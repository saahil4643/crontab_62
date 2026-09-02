#!/usr/bin/env python3
from __future__ import annotations

"""
Server Connectivity & Scraper Health Check.

Tests reachability and scraper response for:
1. Google Sheets API (Authentication + Sheet Read)
2. Alpha Spread (Playwright + HTTP)
3. ValueInvesting.io
4. GuruFocus.com
5. Yahoo Finance
"""

import asyncio
import os
import sys
import time
from pathlib import Path
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import config
from credentials import get_credentials
from sheet_client import DcfSheetClient


def test_http_url(url: str, name: str, headers: dict | None = None) -> tuple[bool, str, float]:
    headers = headers or {
        "User-Agent": config.USER_AGENT
    }
    req = urllib.request.Request(url, headers=headers)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            elapsed = time.time() - t0
            code = resp.getcode()
            return True, f"HTTP {code}", elapsed
    except urllib.error.HTTPError as exc:
        elapsed = time.time() - t0
        return False, f"HTTP {exc.code} ({exc.reason})", elapsed
    except urllib.error.URLError as exc:
        elapsed = time.time() - t0
        return False, f"URLError: {exc.reason}", elapsed
    except Exception as exc:
        elapsed = time.time() - t0
        return False, f"Error: {exc}", elapsed


def test_google_sheets() -> tuple[bool, str, float]:
    t0 = time.time()
    try:
        client = DcfSheetClient()
        ws = client.worksheet()
        all_vals = client.collect_jobs(start_row=3)
        elapsed = time.time() - t0
        return True, f"Connected to '{ws.title}' ({len(all_vals)} jobs queued)", elapsed
    except Exception as exc:
        elapsed = time.time() - t0
        return False, f"Error: {exc}", elapsed


async def test_scrapers_live():
    from models import ScrapeJob
    from resilient_collector.proxy_pool import build_validated_pool
    from resilient_collector.gurufocus_session import GuruFocusSession
    from resilient_collector.valueinvesting_session import ValueInvestingSession
    from resilient_collector.orchestrator import (
        _scrape_alphaspread,
        _scrape_valueinvesting,
        _scrape_gurufocus,
        _scrape_yahoo_group,
    )
    from resilient_collector.scheduler import YahooTickerGroup

    pool = await build_validated_pool()
    gf_session = GuruFocusSession(pool)
    vi_session = ValueInvestingSession(pool)

    results = {}

    print("\n--- Testing Live Scrapers with ticker 'AAPL' ---")

    # 1. Alpha Spread
    print("Testing Alpha Spread (AAPL)...", end=" ", flush=True)
    t0 = time.time()
    try:
        job = ScrapeJob(
            source="alphaspread",
            ticker="AAPL",
            row=3,
            value_col="D",
            value_col_index=4,
            label="Alpha Spread",
            security_type="nasdaq",
        )
        val = await _scrape_alphaspread(job, pool)
        elapsed = time.time() - t0
        status = "OK" if val else "NO VALUE"
        print(f"[{status}] in {elapsed:.1f}s -> DCF: {val}")
        results["Alpha Spread"] = (True if val else False, f"DCF: {val}", elapsed)
    except Exception as exc:
        elapsed = time.time() - t0
        print(f"[FAILED] in {elapsed:.1f}s -> {exc}")
        results["Alpha Spread"] = (False, str(exc), elapsed)

    # 2. ValueInvesting
    print("Testing ValueInvesting (AAPL)...", end=" ", flush=True)
    t0 = time.time()
    try:
        job = ScrapeJob(
            source="valueinvesting",
            ticker="AAPL",
            row=3,
            value_col="I",
            value_col_index=9,
            label="ValueIo",
            security_type="nasdaq",
        )
        val = await _scrape_valueinvesting(job, vi_session)
        elapsed = time.time() - t0
        status = "OK" if val else "NO VALUE"
        print(f"[{status}] in {elapsed:.1f}s -> DCF: {val}")
        results["ValueInvesting"] = (True if val else False, f"DCF: {val}", elapsed)
    except Exception as exc:
        elapsed = time.time() - t0
        print(f"[FAILED] in {elapsed:.1f}s -> {exc}")
        results["ValueInvesting"] = (False, str(exc), elapsed)

    # 3. GuruFocus
    print("Testing GuruFocus (AAPL)...", end=" ", flush=True)
    t0 = time.time()
    try:
        job = ScrapeJob(
            source="gurufocus",
            ticker="AAPL",
            row=3,
            value_col="O",
            value_col_index=15,
            label="GuruFocus",
            security_type="nasdaq",
        )
        val = await _scrape_gurufocus(job, gf_session)
        elapsed = time.time() - t0
        status = "OK" if val else "NO VALUE"
        print(f"[{status}] in {elapsed:.1f}s -> DCF: {val}")
        results["GuruFocus"] = (True if val else False, f"DCF: {val}", elapsed)
    except Exception as exc:
        elapsed = time.time() - t0
        print(f"[FAILED] in {elapsed:.1f}s -> {exc}")
        results["GuruFocus"] = (False, str(exc), elapsed)

    # 4. Yahoo Finance
    print("Testing Yahoo Finance (AAPL)...", end=" ", flush=True)
    t0 = time.time()
    try:
        group = YahooTickerGroup(
            ticker="AAPL",
            security_type="nasdaq",
            jobs=[
                ScrapeJob(source="price_target_low", ticker="AAPL", row=3, value_col="T", value_col_index=20, label="Low Target"),
                ScrapeJob(source="price_target_avg", ticker="AAPL", row=3, value_col="U", value_col_index=21, label="Avg Target"),
                ScrapeJob(source="price_target_high", ticker="AAPL", row=3, value_col="V", value_col_index=22, label="High Target"),
            ]
        )
        val = await _scrape_yahoo_group(group, pool)
        elapsed = time.time() - t0
        status = "OK" if val else "NO VALUE"
        print(f"[{status}] in {elapsed:.1f}s -> Targets: {val}")
        results["Yahoo Finance"] = (True if val else False, f"Targets: {val}", elapsed)
    except Exception as exc:
        elapsed = time.time() - t0
        print(f"[FAILED] in {elapsed:.1f}s -> {exc}")
        results["Yahoo Finance"] = (False, str(exc), elapsed)

    await gf_session.close()
    await vi_session.close()

    return results


def main():
    print("=" * 70)
    print("  CRON-62 SERVER CONNECTIVITY & HEALTH CHECK")
    print("=" * 70)

    # 1. HTTP Endpoint Reachability Check
    endpoints = [
        ("Alpha Spread HTTP", "https://www.alphaspread.com"),
        ("ValueInvesting HTTP", "https://valueinvesting.io"),
        ("GuruFocus HTTP", "https://www.gurufocus.com"),
        ("Yahoo Finance HTTP", "https://finance.yahoo.com"),
    ]

    print("\n--- 1. Testing Raw HTTP Reachability from Server ---")
    for name, url in endpoints:
        ok, msg, elapsed = test_http_url(url, name)
        status_tag = "✓ REACHABLE" if ok else "✗ FAILED"
        print(f"  {name:<22} : {status_tag:<12} ({elapsed:.2f}s) -> {msg}")

    # 2. Google Sheets API Check
    print("\n--- 2. Testing Google Sheets API Connection ---")
    ok, msg, elapsed = test_google_sheets()
    status_tag = "✓ CONNECTED" if ok else "✗ FAILED"
    print(f"  {'Google Sheets API':<22} : {status_tag:<12} ({elapsed:.2f}s) -> {msg}")

    # 3. Live Scraper Check
    try:
        asyncio.run(test_scrapers_live())
    except KeyboardInterrupt:
        print("\nTest cancelled by user.")
    except Exception as exc:
        print(f"\nLive scraper check error: {exc}")

    print("\n" + "=" * 70)
    print("  CHECK COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
