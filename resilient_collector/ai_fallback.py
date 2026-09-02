"""
resilient_collector/ai_fallback.py

Deterministic AI API fallback module for DCF value retrieval in Cron 62.

Architecture:
1. AI API is queried strictly for structured fundamental financial inputs
   (TTM Free Cash Flow, projected growth rate, WACC, perpetual growth rate, cash, debt, shares).
2. Python validates financial input sanity.
3. Deterministic 2-Stage DCF formula executes in Python code.
4. Returns exact intrinsic fair value per share in USD, or None if inputs fail validation.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

import config
from scrapers.extract import normalize_numeric_string

logger = logging.getLogger(__name__)


def validate_dcf_inputs(inputs: dict[str, Any]) -> bool:
    """
    Validate structured financial inputs for Python DCF calculation.
    Returns True only if all required inputs exist, are numeric, and meet economic bounds.
    """
    if not isinstance(inputs, dict):
        logger.warning("[ai_fallback] Validation failed: inputs payload is not a dict")
        return False

    required_keys = (
        "free_cash_flow_ttm",
        "growth_rate_5y_pct",
        "wacc_pct",
        "terminal_growth_pct",
        "total_cash",
        "total_debt",
        "shares_outstanding",
    )

    for key in required_keys:
        val = inputs.get(key)
        if val is None or isinstance(val, bool):
            logger.warning("[ai_fallback] Validation failed: missing or invalid field '%s'=%r", key, val)
            return False
        try:
            float(val)
        except (ValueError, TypeError):
            logger.warning("[ai_fallback] Validation failed: field '%s'=%r is not a number", key, val)
            return False

    fcf = float(inputs["free_cash_flow_ttm"])
    growth = float(inputs["growth_rate_5y_pct"])
    wacc = float(inputs["wacc_pct"])
    t_growth = float(inputs["terminal_growth_pct"])
    cash = float(inputs["total_cash"])
    debt = float(inputs["total_debt"])
    shares = float(inputs["shares_outstanding"])

    if fcf <= 0.0:
        logger.warning("[ai_fallback] Validation failed: non-positive FCF TTM (%f)", fcf)
        return False

    if shares <= 0.0:
        logger.warning("[ai_fallback] Validation failed: non-positive shares outstanding (%f)", shares)
        return False

    if wacc <= t_growth:
        logger.warning("[ai_fallback] Validation failed: WACC (%f%%) <= terminal growth (%f%%)", wacc, t_growth)
        return False

    if not (3.0 <= wacc <= 25.0):
        logger.warning("[ai_fallback] Validation failed: WACC (%f%%) outside expected range [3%%, 25%%]", wacc)
        return False

    if not (-30.0 <= growth <= 100.0):
        logger.warning("[ai_fallback] Validation failed: 5Y growth (%f%%) outside range [-30%%, 100%%]", growth)
        return False

    if not (0.0 <= t_growth <= 6.0):
        logger.warning("[ai_fallback] Validation failed: terminal growth (%f%%) outside range [0%%, 6%%]", t_growth)
        return False

    if cash < 0.0 or debt < 0.0:
        logger.warning("[ai_fallback] Validation failed: negative cash (%f) or debt (%f)", cash, debt)
        return False

    return True


def calculate_dcf_in_python(inputs: dict[str, Any]) -> float | None:
    """
    Deterministically calculate the intrinsic DCF fair value per share in USD
    using a 2-stage Discounted Cash Flow valuation model.
    """
    if not validate_dcf_inputs(inputs):
        return None

    fcf_0 = float(inputs["free_cash_flow_ttm"])
    g_5y = float(inputs["growth_rate_5y_pct"]) / 100.0
    r = float(inputs["wacc_pct"]) / 100.0
    g_term = float(inputs["terminal_growth_pct"]) / 100.0
    cash = float(inputs["total_cash"])
    debt = float(inputs["total_debt"])
    shares = float(inputs["shares_outstanding"])

    # 1. Present Value of Projected 5-Year Free Cash Flows
    pv_fcfs = 0.0
    current_fcf = fcf_0
    for year in range(1, 6):
        current_fcf *= (1.0 + g_5y)
        pv_fcfs += current_fcf / ((1.0 + r) ** year)

    # 2. Terminal Value & Present Value of Terminal Value
    terminal_value = (current_fcf * (1.0 + g_term)) / (r - g_term)
    pv_terminal_value = terminal_value / ((1.0 + r) ** 5)

    # 3. Enterprise Value & Equity Value
    enterprise_value = pv_fcfs + pv_terminal_value
    equity_value = enterprise_value + cash - debt

    if equity_value <= 0.0:
        logger.warning("[ai_fallback] DCF calculation produced non-positive equity value: %f", equity_value)
        return None

    # 4. Fair Value Per Share
    fair_value_per_share = equity_value / shares

    if fair_value_per_share <= 0.01 or fair_value_per_share > 100000.0:
        logger.warning("[ai_fallback] DCF fair value per share out of sanity bounds: %f", fair_value_per_share)
        return None

    return fair_value_per_share


def validate_ai_dcf_value(raw_val: Any) -> str | None:
    """
    Validate numeric string formatting for DCF fair value per share.
    """
    if raw_val is None:
        return None

    normalized = normalize_numeric_string(str(raw_val))
    if normalized is None:
        return None

    try:
        val_float = float(normalized)
    except (ValueError, TypeError):
        return None

    if val_float <= 0.01 or val_float > 100000.0:
        return None

    return normalized


def _strip_markdown_codeblocks(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 2 and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


async def fetch_dcf_ai_fallback(ticker: str, source_label: str) -> str | None:
    """
    Query AI API for fundamental financial model inputs for *ticker* and compute
    the deterministic 2-stage DCF fair value per share in Python code.
    """
    if not config.AI_FALLBACK_ENABLED:
        logger.debug("[%s] AI DCF fallback disabled via config", ticker)
        return None

    api_key = config.AI_FALLBACK_API_KEY
    if not api_key:
        logger.warning(
            "[%s] AI_FALLBACK_API_KEY not set in environment; skipping AI fallback for %s",
            ticker,
            source_label,
        )
        return None

    model = config.AI_FALLBACK_MODEL
    base_url = config.AI_FALLBACK_BASE_URL.rstrip("/")
    url = f"{base_url}/chat/completions"
    timeout = config.AI_FALLBACK_TIMEOUT_SECONDS

    prompt = (
        f"Fetch key fundamental financial figures for stock ticker '{ticker}' required for a 2-stage DCF valuation.\n"
        f"Respond ONLY with a valid JSON object matching this exact schema:\n"
        f"{{\n"
        f'  "ticker": "{ticker}",\n'
        f'  "free_cash_flow_ttm": <TTM_FREE_CASH_FLOW_IN_USD_NUMBER>,\n'
        f'  "growth_rate_5y_pct": <ANNUAL_FCF_GROWTH_RATE_PERCENT_NUMBER>,\n'
        f'  "wacc_pct": <DISCOUNT_RATE_WACC_PERCENT_NUMBER>,\n'
        f'  "terminal_growth_pct": <PERPETUAL_TERMINAL_GROWTH_PERCENT_NUMBER>,\n'
        f'  "total_cash": <CASH_AND_SHORT_TERM_INVESTMENTS_USD_NUMBER>,\n'
        f'  "total_debt": <TOTAL_DEBT_USD_NUMBER>,\n'
        f'  "shares_outstanding": <DILUTED_SHARES_OUTSTANDING_NUMBER>\n'
        f"}}\n"
        f"Rules:\n"
        f"1. Use numbers only (no strings with '$' or '%').\n"
        f"2. Use recent TTM / 10-K data.\n"
        f"3. Do NOT include markdown formatting or commentary outside JSON.\n"
        f"4. If reliable financial data is unavailable for '{ticker}', set \"free_cash_flow_ttm\": null."
    )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a quantitative financial database. "
                    "Extract and return exact structured fundamental financial data in valid JSON."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.0,
    }

    logger.info(
        "[%s] Initiating AI DCF data fallback for source '%s' (model=%s, temp=0.0)",
        ticker,
        source_label,
        model,
    )

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        choices = data.get("choices", [])
        if not choices:
            logger.warning("[%s] AI API returned empty choices for %s", ticker, source_label)
            return None

        raw_content = choices[0].get("message", {}).get("content", "")
        cleaned_content = _strip_markdown_codeblocks(raw_content)

        try:
            parsed_inputs = json.loads(cleaned_content)
        except json.JSONDecodeError:
            logger.warning("[%s] AI response was not valid JSON for DCF inputs", ticker)
            return None

        # Execute deterministic Python calculation
        calculated_dcf = calculate_dcf_in_python(parsed_inputs)
        if calculated_dcf is None:
            logger.warning("[%s] Python DCF calculation failed or inputs invalid for %s", ticker, source_label)
            return None

        validated_str = validate_ai_dcf_value(calculated_dcf)
        if validated_str is not None:
            logger.info(
                "[%s] Deterministic Python DCF calculation succeeded for %s: fair_value=%s "
                "(inputs: FCF=%.2fe6, Growth=%.1f%%, WACC=%.1f%%, Shares=%.2fe6)",
                ticker,
                source_label,
                validated_str,
                float(parsed_inputs["free_cash_flow_ttm"]) / 1e6,
                float(parsed_inputs["growth_rate_5y_pct"]),
                float(parsed_inputs["wacc_pct"]),
                float(parsed_inputs["shares_outstanding"]) / 1e6,
            )
            return validated_str

        return None

    except httpx.HTTPStatusError as exc:
        logger.error(
            "[%s] AI API HTTP error for %s: status=%s detail=%s",
            ticker,
            source_label,
            exc.response.status_code,
            exc.response.text[:200],
        )
        return None
    except httpx.TimeoutException:
        logger.error("[%s] AI API request timed out after %.1fs for %s", ticker, timeout, source_label)
        return None
    except Exception as exc:
        logger.error("[%s] AI API request failed for %s: %s", ticker, source_label, exc)
        return None
