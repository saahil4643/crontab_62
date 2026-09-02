"""
resilient_collector/orchestrator.py

Main async orchestrator for the sheet collector.

Exports:
    SHEET_SOURCES : dict[SourceKey, str]  -- all supported source keys
    run_sheet_collector(...)              -- top-level async coroutine
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
from pathlib import Path
from typing import TYPE_CHECKING

from config import MISSING_VALUE_BLOCKS, SourceKey
from models import ScrapeJob
from resilient_collector.progress_tracker import clear_progress, mark_completed
from resilient_collector.proxy_pool import build_validated_pool
from resilient_collector.scheduler import (
    ROUND_ROBIN_ORDER,
    YahooTickerGroup,
    any_queue_nonempty,
    is_yahoo_source,
    partition_scrape_queues,
    queue_remaining_summary,
    take_chunk,
)
from sheet_client import DcfSheetClient
from sheet_write_buffer import SheetWriteBuffer

if TYPE_CHECKING:
    from worker_shutdown import ShutdownController

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT / "logs"
PENDING_WRITES_FILE = LOG_DIR / "pending_writes.jsonl"

# --------------------------------------------------------------------------
# Public registry: all source keys this collector understands.
# --------------------------------------------------------------------------

SHEET_SOURCES: dict[SourceKey, str] = {
    "alphaspread": "Alpha Spread DCF",
    "valueinvesting": "ValueInvesting DCF",
    "gurufocus": "GuruFocus DCF",
    "price_target_low": "Yahoo Price Target Low",
    "price_target_avg": "Yahoo Price Target Average",
    "price_target_high": "Yahoo Price Target High",
}

# --------------------------------------------------------------------------
# Per-source scrape chunk sizes
# --------------------------------------------------------------------------

_CHUNK_SIZE_ALPHASPREAD: int = int(os.environ.get("CHUNK_SIZE_ALPHASPREAD", "5"))
_CHUNK_SIZE_VALUEINVESTING: int = int(os.environ.get("CHUNK_SIZE_VALUEINVESTING", "3"))
_CHUNK_SIZE_GURUFOCUS: int = int(os.environ.get("CHUNK_SIZE_GURUFOCUS", "5"))
_CHUNK_SIZE_YAHOO: int = int(os.environ.get("CHUNK_SIZE_YAHOO", "5"))

_CHUNK_SIZES: dict[str, int] = {
    "alphaspread": _CHUNK_SIZE_ALPHASPREAD,
    "valueinvesting": _CHUNK_SIZE_VALUEINVESTING,
    "gurufocus": _CHUNK_SIZE_GURUFOCUS,
    "yahoo": _CHUNK_SIZE_YAHOO,
}

# Anti-ban delay (seconds) between individual stock requests to protect VPS IP
_SCRAPE_DELAY_SECONDS: float = float(os.environ.get("SCRAPE_DELAY_SECONDS", "5.0"))
_SCRAPE_DELAY_JITTER_SECONDS: float = float(os.environ.get("SCRAPE_DELAY_JITTER_SECONDS", "1.5"))

# Inter-chunk delay (seconds) to avoid hammering sites
_INTER_CHUNK_DELAY: float = float(os.environ.get("RESILIENT_INTER_CHUNK_DELAY_SECONDS", "2"))


async def _sleep_between_stocks(shutdown: ShutdownController, label: str = "") -> None:
    if shutdown.is_requested():
        return
    delay = _SCRAPE_DELAY_SECONDS
    if _SCRAPE_DELAY_JITTER_SECONDS > 0:
        delay += random.uniform(0.0, _SCRAPE_DELAY_JITTER_SECONDS)
    if delay <= 0:
        return
    logger.info(
        "[ANTI-BAN DELAY] Pausing %.1fs before next request (%s) to protect VPS IP...",
        delay,
        label,
    )
    from resilient_collector.nav_retry import interruptible_sleep_seconds
    await interruptible_sleep_seconds(delay, shutdown)


# --------------------------------------------------------------------------
# Scraper dispatch
# --------------------------------------------------------------------------


async def _scrape_alphaspread(job: ScrapeJob, proxy_pool: list) -> str | None:
    """Scrape Alpha Spread DCF value for *job.ticker*."""
    from config import ALPHA_SPREAD_URL, USER_AGENT
    from resilient_collector.nav_retry import goto_with_retry
    from scrapers import extract_from_json_payloads, extract_from_text
    from config import DCF_JSON_KEY_HINTS, DCF_TEXT_REGEX_PATTERNS, JSON_URL_HINTS_ALPHASPREAD
    from resilient_collector.proxy_pool import ProxyConfig
    from playwright.async_api import async_playwright

    url = ALPHA_SPREAD_URL.format(
        security_type=job.security_type,
        ticker=job.ticker.lower(),
    )
    timeout_ms = int(os.environ.get("SCRAPE_TIMEOUT_MS", "30000"))

    json_payloads: list = []

    async with async_playwright() as pw:
        proxy_cfg = proxy_pool[0] if proxy_pool else ProxyConfig()
        launch_kwargs: dict = {"headless": True}
        browser = await pw.chromium.launch(**launch_kwargs)
        context_kwargs: dict = {"user_agent": USER_AGENT}
        if proxy_cfg.playwright_config:
            context_kwargs["proxy"] = proxy_cfg.playwright_config
        ctx = await browser.new_context(**context_kwargs)
        page = await ctx.new_page()

        async def _capture(response) -> None:
            try:
                u = response.url.lower()
                if any(h in u for h in JSON_URL_HINTS_ALPHASPREAD):
                    try:
                        body = await response.json()
                        json_payloads.append(body)
                    except Exception:
                        pass
            except Exception:
                pass

        page.on("response", _capture)

        try:
            await goto_with_retry(
                page, url, ticker=job.ticker, label="alphaspread", timeout_ms=timeout_ms
            )
            await page.wait_for_timeout(3500)
            content = await page.content()
        finally:
            await page.close()
            await ctx.close()
            await browser.close()

    value = extract_from_text(content, DCF_TEXT_REGEX_PATTERNS)
    if value is None:
        value = extract_from_json_payloads(json_payloads, DCF_JSON_KEY_HINTS)
    return value


async def _scrape_valueinvesting(
    job: ScrapeJob,
    vi_session,
) -> str | None:
    from config import VALUE_INVESTING_PATHS, VALUE_INVESTING_VALUATION_URL
    from config import DCF_JSON_KEY_HINTS, DCF_TEXT_REGEX_PATTERNS, JSON_URL_HINTS_VALUEINVESTING
    from resilient_collector.nav_retry import goto_with_retry
    from resilient_collector.valueinvesting_errors import ValueInvestingLimitError
    from scrapers import extract_from_json_payloads, extract_from_text

    timeout_ms = int(os.environ.get("SCRAPE_TIMEOUT_MS", "30000"))

    for path in VALUE_INVESTING_PATHS:
        url = VALUE_INVESTING_VALUATION_URL.format(ticker=job.ticker, path=path)
        json_payloads: list = []
        page = await vi_session.ensure_page()

        async def _capture(response) -> None:
            try:
                u = response.url.lower()
                if any(h in u for h in JSON_URL_HINTS_VALUEINVESTING):
                    try:
                        body = await response.json()
                        json_payloads.append(body)
                    except Exception:
                        pass
            except Exception:
                pass

        page.on("response", _capture)
        try:
            await goto_with_retry(
                page, url, ticker=job.ticker, label="valueinvesting", timeout_ms=timeout_ms
            )
            await page.wait_for_timeout(1500)
            content = await page.content()
        except Exception:
            page.remove_listener("response", _capture)
            raise

        page.remove_listener("response", _capture)

        # Detect signup wall / view limit
        content_lower = content.lower()
        if (
            "signup" in content_lower
            or "sign up" in content_lower
            or "pricing/login" in content_lower
            or "view limit" in content_lower
        ):
            raise ValueInvestingLimitError(
                f"[{job.ticker}] valueinvesting signup wall / view limit at {url}"
            )

        vi_session.record_view()

        value = extract_from_json_payloads(json_payloads, DCF_JSON_KEY_HINTS)
        if value is None:
            value = extract_from_text(content, DCF_TEXT_REGEX_PATTERNS)
        if value is not None:
            return value

    return None


async def _scrape_gurufocus(job: ScrapeJob, gf_session) -> str | None:
    from config import GURUFOCUS_DCF_URL, GURUFOCUS_EARNINGS_TERM_URL
    from config import DCF_JSON_KEY_HINTS, DCF_TEXT_REGEX_PATTERNS
    from resilient_collector.nav_retry import goto_with_retry
    from scrapers import extract_from_json_payloads, extract_from_text

    timeout_ms = int(os.environ.get("SCRAPE_TIMEOUT_MS", "30000"))
    json_payloads: list = []

    page = await gf_session.ensure_page()

    async def _capture(response) -> None:
        try:
            u = response.url.lower()
            if "gurufocus" in u and ("dcf" in u or "valuation" in u or "term" in u):
                try:
                    body = await response.json()
                    json_payloads.append(body)
                except Exception:
                    pass
        except Exception:
            pass

    page.on("response", _capture)
    try:
        url = GURUFOCUS_DCF_URL.format(ticker=job.ticker)
        resp = await goto_with_retry(
            page, url, ticker=job.ticker, label="gurufocus_dcf", timeout_ms=timeout_ms
        )
        await page.wait_for_timeout(2000)

        status = resp.status if resp is not None else None
        if status == 403:
            logger.warning("[%s] GuruFocus 403 on DCF page; escalating to headed", job.ticker)
            await gf_session.escalate_to_headed()
            page = await gf_session.ensure_page()
            page.on("response", _capture)
            await goto_with_retry(
                page, url, ticker=job.ticker, label="gurufocus_dcf_headed", timeout_ms=timeout_ms
            )
            await page.wait_for_timeout(2000)

        content = await page.content()
    except Exception:
        page.remove_listener("response", _capture)
        raise

    page.remove_listener("response", _capture)
    gf_session.record_view()

    value = extract_from_json_payloads(json_payloads, DCF_JSON_KEY_HINTS)
    if value is None:
        value = extract_from_text(content, DCF_TEXT_REGEX_PATTERNS)

    if value is None:
        # Fallback: earnings term page
        try:
            fallback_url = GURUFOCUS_EARNINGS_TERM_URL.format(ticker=job.ticker)
            json_payloads2: list = []
            page2 = await gf_session.ensure_page()

            async def _cap2(response) -> None:
                try:
                    body = await response.json()
                    json_payloads2.append(body)
                except Exception:
                    pass

            page2.on("response", _cap2)
            await goto_with_retry(
                page2, fallback_url, ticker=job.ticker,
                label="gurufocus_term", timeout_ms=timeout_ms,
            )
            await page2.wait_for_timeout(1500)
            content2 = await page2.content()
            page2.remove_listener("response", _cap2)
            value = extract_from_json_payloads(json_payloads2, DCF_JSON_KEY_HINTS)
            if value is None:
                value = extract_from_text(content2, DCF_TEXT_REGEX_PATTERNS)
        except Exception as exc:
            logger.debug("[%s] gurufocus term fallback failed: %s", job.ticker, exc)

    return value


async def _scrape_yahoo_group(
    group: YahooTickerGroup,
    proxy_pool: list,
) -> dict[str, str | None]:
    """
    Fetch Yahoo Finance analyst page once for *group.ticker*, extract
    price-target low/avg/high from network responses, and return a dict
    mapping source key -> value.
    """
    from config import (
        YAHOO_QUOTE_URL,
        PRICE_TARGET_JSON_KEY_HINTS,
        PRICE_TARGET_TEXT_REGEX,
    )
    from resilient_collector.nav_retry import goto_with_retry
    from resilient_collector.proxy_pool import ProxyConfig
    from scrapers import extract_from_json_payloads, extract_from_text
    from playwright.async_api import async_playwright

    ticker = group.ticker
    url = YAHOO_QUOTE_URL.format(ticker=ticker)
    timeout_ms = int(os.environ.get("SCRAPE_TIMEOUT_MS", "30000"))

    json_payloads: list = []
    content = ""

    proxy_cfg = proxy_pool[0] if proxy_pool else ProxyConfig()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context_kwargs: dict = {
            "locale": "en-US",
        }
        if proxy_cfg.playwright_config:
            context_kwargs["proxy"] = proxy_cfg.playwright_config
        ctx = await browser.new_context(**context_kwargs)
        page = await ctx.new_page()

        async def _capture(response) -> None:
            try:
                u = response.url.lower()
                if "finance.yahoo.com" in u and (
                    "quotesummary" in u or "analystratings" in u or "pricetarget" in u
                ):
                    try:
                        body = await response.json()
                        json_payloads.append(body)
                    except Exception:
                        pass
            except Exception:
                pass

        page.on("response", _capture)
        try:
            await goto_with_retry(
                page, url, ticker=ticker, label="yahoo", timeout_ms=timeout_ms
            )
            await page.wait_for_timeout(2000)
            content = await page.content()
        finally:
            await page.close()
            await ctx.close()
            await browser.close()

    results: dict[str, str | None] = {}
    for variant, hints in PRICE_TARGET_JSON_KEY_HINTS.items():
        source_key = f"price_target_{variant}"
        val = extract_from_json_payloads(json_payloads, hints)
        if val is None:
            patterns = PRICE_TARGET_TEXT_REGEX.get(variant, ())
            val = extract_from_text(content, patterns)
        results[source_key] = val

    return results


# --------------------------------------------------------------------------
# Chunk processors
# --------------------------------------------------------------------------


async def _process_alphaspread_chunk(
    jobs: list[ScrapeJob],
    buffer: SheetWriteBuffer,
    proxy_pool: list,
    shutdown: ShutdownController,
) -> None:
    for job in jobs:
        if shutdown.is_requested():
            return
        if job.clear_only:
            await buffer.enqueue_clear(job)
            mark_completed(job.source, job.row)
            continue

        logger.info(
            "[SCRAPING] Row %d | Col %s | %s | Source: Alpha Spread",
            job.row,
            job.value_col,
            job.ticker,
        )
        value = None
        try:
            value = await _scrape_alphaspread(job, proxy_pool)
        except Exception as exc:
            logger.error("[%s] alphaspread scrape error: %s", job.ticker, exc)

        if value is not None:
            from scrapers import format_for_sheet
            formatted = format_for_sheet(value)
            logger.info("[SCRAPE SUCCESS] %s | Alpha Spread = %s", job.ticker, formatted)
            await buffer.enqueue_write(job, formatted)
        else:
            logger.warning(
                "[%s] alphaspread: primary scraper returned no value; triggering AI DCF fallback",
                job.ticker,
            )
            from resilient_collector.ai_fallback import fetch_dcf_ai_fallback
            ai_value = await fetch_dcf_ai_fallback(job.ticker, job.label)
            if ai_value is not None:
                from scrapers import format_for_sheet
                formatted_ai = format_for_sheet(ai_value)
                logger.info("[SCRAPE AI FALLBACK] %s | Alpha Spread = %s", job.ticker, formatted_ai)
                await buffer.enqueue_write(job, formatted_ai)
            else:
                logger.warning(
                    "[%s] alphaspread: no valid DCF value from primary scraper or AI fallback",
                    job.ticker,
                )
        mark_completed(job.source, job.row)
        await _sleep_between_stocks(shutdown, f"{job.ticker} (alphaspread)")


async def _process_valueinvesting_chunk(
    jobs: list[ScrapeJob],
    buffer: SheetWriteBuffer,
    vi_session,
    shutdown: ShutdownController,
) -> None:
    from resilient_collector.valueinvesting_errors import ValueInvestingLimitError

    for job in jobs:
        if shutdown.is_requested():
            return
        if job.clear_only:
            await buffer.enqueue_clear(job)
            mark_completed(job.source, job.row)
            continue

        logger.info(
            "[SCRAPING] Row %d | Col %s | %s | Source: ValueInvesting",
            job.row,
            job.value_col,
            job.ticker,
        )
        value = None
        try:
            value = await _scrape_valueinvesting(job, vi_session)
        except ValueInvestingLimitError as exc:
            logger.warning("[%s] valueinvesting limit: %s", job.ticker, exc)
            # Rotate identity to get a fresh view budget
            await vi_session.rotate_identity()
        except Exception as exc:
            logger.error("[%s] valueinvesting scrape error: %s", job.ticker, exc)

        if value is not None:
            from scrapers import format_for_sheet
            formatted = format_for_sheet(value)
            logger.info("[SCRAPE SUCCESS] %s | ValueInvesting = %s", job.ticker, formatted)
            await buffer.enqueue_write(job, formatted)
        else:
            logger.warning(
                "[%s] valueinvesting: primary scraper returned no value; triggering AI DCF fallback",
                job.ticker,
            )
            from resilient_collector.ai_fallback import fetch_dcf_ai_fallback
            ai_value = await fetch_dcf_ai_fallback(job.ticker, job.label)
            if ai_value is not None:
                from scrapers import format_for_sheet
                formatted_ai = format_for_sheet(ai_value)
                logger.info("[SCRAPE AI FALLBACK] %s | ValueInvesting = %s", job.ticker, formatted_ai)
                await buffer.enqueue_write(job, formatted_ai)
            else:
                logger.warning(
                    "[%s] valueinvesting: no valid DCF value from primary scraper or AI fallback",
                    job.ticker,
                )
        mark_completed(job.source, job.row)
        await _sleep_between_stocks(shutdown, f"{job.ticker} (valueinvesting)")


async def _process_gurufocus_chunk(
    jobs: list[ScrapeJob],
    buffer: SheetWriteBuffer,
    gf_session,
    shutdown: ShutdownController,
) -> None:
    for job in jobs:
        if shutdown.is_requested():
            return
        if job.clear_only:
            await buffer.enqueue_clear(job)
            mark_completed(job.source, job.row)
            continue

        logger.info(
            "[SCRAPING] Row %d | Col %s | %s | Source: GuruFocus",
            job.row,
            job.value_col,
            job.ticker,
        )
        value = None
        try:
            value = await _scrape_gurufocus(job, gf_session)
        except Exception as exc:
            logger.error("[%s] gurufocus scrape error: %s", job.ticker, exc)

        if value is not None:
            from scrapers import format_for_sheet
            formatted = format_for_sheet(value)
            logger.info("[SCRAPE SUCCESS] %s | GuruFocus = %s", job.ticker, formatted)
            await buffer.enqueue_write(job, formatted)
        else:
            logger.warning(
                "[%s] gurufocus: primary scraper returned no value; triggering AI DCF fallback",
                job.ticker,
            )
            from resilient_collector.ai_fallback import fetch_dcf_ai_fallback
            ai_value = await fetch_dcf_ai_fallback(job.ticker, job.label)
            if ai_value is not None:
                from scrapers import format_for_sheet
                formatted_ai = format_for_sheet(ai_value)
                logger.info("[SCRAPE AI FALLBACK] %s | GuruFocus = %s", job.ticker, formatted_ai)
                await buffer.enqueue_write(job, formatted_ai)
            else:
                logger.warning(
                    "[%s] gurufocus: no valid DCF value from primary scraper or AI fallback",
                    job.ticker,
                )
        mark_completed(job.source, job.row)
        await _sleep_between_stocks(shutdown, f"{job.ticker} (gurufocus)")


async def _process_yahoo_chunk(
    groups: list[YahooTickerGroup],
    buffer: SheetWriteBuffer,
    proxy_pool: list,
    shutdown: ShutdownController,
) -> None:
    for group in groups:
        if shutdown.is_requested():
            return
        logger.info("[SCRAPING] Stock: %s | Source: Yahoo Targets", group.ticker)
        try:
            results = await _scrape_yahoo_group(group, proxy_pool)
            from scrapers import format_for_sheet
            for job in group.jobs:
                value = results.get(job.source)
                if value is not None:
                    formatted = format_for_sheet(value)
                    logger.info("[SCRAPE SUCCESS] %s | %s = %s", job.ticker, job.label, formatted)
                    await buffer.enqueue_write(job, formatted)
                else:
                    logger.warning("[%s] yahoo %s: no value found", job.ticker, job.source)
                mark_completed(job.source, job.row)
        except Exception as exc:
            logger.error("[%s] yahoo scrape error: %s", group.ticker, exc)
        await _sleep_between_stocks(shutdown, f"{group.ticker} (yahoo)")


# --------------------------------------------------------------------------
# Main entry point
# --------------------------------------------------------------------------


async def run_sheet_collector(
    *,
    dry_run: bool = False,
    limit: int | None = None,
    sources: set[SourceKey] | None = None,
    shutdown: ShutdownController,
) -> list[ScrapeJob]:
    """
    Top-level orchestrator coroutine.

    1. Read the Google Sheet to build scrape jobs.
    2. Filter by *sources* and *limit* (if given).
    3. Partition into per-source queues.
    4. Round-robin through queues until empty or shutdown requested.
    5. Flush remaining buffered writes.

    Returns the list of all ScrapeJob objects that were queued (not just completed).
    """
    logger.info(
        "run_sheet_collector | dry_run=%s | limit=%s | sources=%s",
        dry_run, limit, sources,
    )

    # --- Build proxy pool ------------------------------------------------
    proxy_pool = await build_validated_pool()

    # Clear per-cycle progress so we process all current jobs fresh
    clear_progress()

    # --- Read sheet jobs -------------------------------------------------
    sheet_client = await asyncio.to_thread(DcfSheetClient)
    all_jobs: list[ScrapeJob] = await asyncio.to_thread(sheet_client.collect_jobs)

    # Filter by selected sources
    if sources is not None:
        all_jobs = [j for j in all_jobs if j.source in sources]

    # Apply limit
    if limit is not None:
        all_jobs = all_jobs[:limit]

    logger.info("Total jobs after filter: %d", len(all_jobs))

    if dry_run:
        logger.info("DRY RUN — listing jobs only, no scraping or writing")
        for job in all_jobs:
            logger.info(
                "  [dry_run] row=%d ticker=%s source=%s col=%s clear_only=%s",
                job.row, job.ticker, job.source, job.value_col, job.clear_only,
            )
        return all_jobs

    if not all_jobs:
        logger.info("No jobs to process")
        return []

    # --- Build sessions --------------------------------------------------
    from resilient_collector.gurufocus_session import GuruFocusSession
    from resilient_collector.valueinvesting_session import ValueInvestingSession

    gf_session = GuruFocusSession(proxy_pool)
    vi_session = ValueInvestingSession(proxy_pool)

    # --- Sheet write buffer ----------------------------------------------
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    buffer = SheetWriteBuffer(sheet_client, pending_path=PENDING_WRITES_FILE)

    # Replay any writes that failed in a previous run
    try:
        replayed = await buffer.replay_pending_file()
        if replayed:
            logger.info("Replayed %d pending writes from previous run", replayed)
    except Exception as exc:
        logger.warning("replay_pending_file failed: %s", exc)

    # --- Partition into queues -------------------------------------------
    queues = partition_scrape_queues(all_jobs)
    logger.info("Queue sizes: %s", queue_remaining_summary(queues))

    # --- Round-robin processing ------------------------------------------
    try:
        while any_queue_nonempty(queues) and not shutdown.is_requested():
            made_progress = False
            for source_name in ROUND_ROBIN_ORDER:
                if shutdown.is_requested():
                    break
                queue = queues.get(source_name)
                if not queue:
                    continue

                chunk_size = _CHUNK_SIZES.get(source_name, 5)
                chunk = take_chunk(queue, chunk_size)
                if not chunk:
                    continue

                made_progress = True
                logger.info(
                    "Processing %d %s job(s) | remaining: %s",
                    len(chunk), source_name, queue_remaining_summary(queues),
                )

                if source_name == "alphaspread":
                    await _process_alphaspread_chunk(chunk, buffer, proxy_pool, shutdown)
                elif source_name == "valueinvesting":
                    await _process_valueinvesting_chunk(chunk, buffer, vi_session, shutdown)
                elif source_name == "gurufocus":
                    await _process_gurufocus_chunk(chunk, buffer, gf_session, shutdown)
                elif source_name == "yahoo":
                    await _process_yahoo_chunk(chunk, buffer, proxy_pool, shutdown)

                if _INTER_CHUNK_DELAY > 0 and not shutdown.is_requested():
                    await asyncio.sleep(_INTER_CHUNK_DELAY)

            if not made_progress:
                # All queues are empty — exit the loop
                break

    finally:
        # Always flush remaining writes and close sessions
        try:
            await buffer.close()
        except Exception as exc:
            logger.error("buffer.close error: %s", exc)
        try:
            await gf_session.close()
        except Exception as exc:
            logger.debug("gf_session.close: %s", exc)
        try:
            await vi_session.close()
        except Exception as exc:
            logger.debug("vi_session.close: %s", exc)

    remaining = sum(len(q) for q in queues.values())
    if remaining:
        logger.warning("%d job(s) not processed (shutdown or error)", remaining)
    else:
        logger.info("All queues drained successfully")

    return all_jobs
