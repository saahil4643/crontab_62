"""
scratch/trace_1000.py

Trace exact JSON key path where walk_json_for_value extracts 1000 for ValueInvesting.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config
from scrapers.extract import walk_json_for_value, _key_matches, _coerce_number


async def trace_vi(ticker: str = "AAPL"):
    from playwright.async_api import async_playwright
    url = f"https://valueinvesting.io/{ticker}/valuation/dcf-growth-exit-5y"
    print(f"\n--- Tracing ValueInvesting 1000 for {ticker} ---")
    json_payloads = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(user_agent=config.USER_AGENT)
        page = await ctx.new_page()

        async def _cap(resp):
            u = resp.url.lower()
            if any(h in u for h in config.JSON_URL_HINTS_VALUEINVESTING):
                try:
                    b = await resp.json()
                    json_payloads.append((u, b))
                except Exception:
                    pass

        page.on("response", _cap)
        try:
            await page.goto(url, timeout=30000, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)

            print(f"Captured {len(json_payloads)} matching responses")
            for u, body in json_payloads:
                print(f"\nCaptured URL: {u}")

                def _debug_walk(obj, depth=0, path=""):
                    if depth > 14:
                        return None
                    if isinstance(obj, dict):
                        for k, v in obj.items():
                            curr_path = f"{path}.{k}" if path else str(k)
                            if isinstance(k, str) and _key_matches(k, config.DCF_JSON_KEY_HINTS):
                                coerced = _coerce_number(v)
                                print(f"  [MATCH] key={curr_path!r} -> val={v!r} (coerced={coerced!r})")
                            _debug_walk(v, depth+1, curr_path)
                    elif isinstance(obj, list):
                        for idx, item in enumerate(obj):
                            _debug_walk(item, depth+1, f"{path}[{idx}]")

                _debug_walk(body)

        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(trace_vi("AAPL"))
