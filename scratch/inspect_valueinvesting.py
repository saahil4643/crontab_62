"""
scratch/inspect_valueinvesting.py

Detailed analysis of ValueInvesting response payloads and text to trace '1000'.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config
from scrapers.extract import walk_json_for_value, _coerce_number, _key_matches


async def inspect_vi(ticker: str = "AAPL"):
    from playwright.async_api import async_playwright
    url = f"https://valueinvesting.io/{ticker}/valuation/dcf-growth-exit-5y"
    print(f"\n--- Inspecting ValueInvesting for {ticker} ---")
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
            await page.wait_for_timeout(2000)

            print(f"Captured {len(json_payloads)} JSON payloads")
            for u, body in json_payloads:
                print(f"\nURL: {u}")
                # Search where 1000 appears in body
                def _find_key_paths(obj, path=""):
                    if isinstance(obj, dict):
                        for k, v in obj.items():
                            new_path = f"{path}.{k}" if path else k
                            if str(v) == "1000" or str(v) == "1000.0":
                                print(f"  FOUND 1000 at path: {new_path}")
                            if _key_matches(str(k), config.DCF_JSON_KEY_HINTS):
                                print(f"  KEY MATCH: {new_path} = {v}")
                            _find_key_paths(v, new_path)
                    elif isinstance(obj, list):
                        for idx, item in enumerate(obj):
                            _find_key_paths(item, f"{path}[{idx}]")

                _find_key_paths(body)

        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(inspect_vi("AAPL"))
