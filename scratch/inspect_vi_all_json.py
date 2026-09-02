"""
scratch/inspect_vi_all_json.py

Capture EVERY JSON network response during ValueInvesting page load.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config
from scrapers.extract import walk_json_for_value, _key_matches


async def dump_all_json(ticker: str = "AAPL"):
    from playwright.async_api import async_playwright
    url = f"https://valueinvesting.io/{ticker}/valuation/dcf-growth-exit-5y"
    print(f"\n--- Intercepting ALL XHR/fetch responses for ValueInvesting ({ticker}) ---")
    json_responses = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(user_agent=config.USER_AGENT)
        page = await ctx.new_page()

        async def _cap(resp):
            try:
                if "json" in resp.headers.get("content-type", "") or resp.url.endswith(".json"):
                    b = await resp.json()
                    json_responses.append((resp.url, b))
            except Exception:
                pass

        page.on("response", _cap)
        try:
            await page.goto(url, timeout=30000, wait_until="networkidle")
            print(f"Captured {len(json_responses)} total JSON network responses")
            for u, body in json_responses:
                print(f"\nURL: {u}")
                val = walk_json_for_value(body, config.DCF_JSON_KEY_HINTS)
                print(f"  walk_json_for_value -> {val}")

                # Search where 1000 appears
                s = str(body)
                if "1000" in s:
                    print("  FOUND '1000' in this JSON response!")

        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(dump_all_json("AAPL"))
