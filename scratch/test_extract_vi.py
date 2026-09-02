"""
scratch/test_extract_vi.py

Exact breakdown of extract_from_text on ValueInvesting HTML for AAPL and MSFT.
"""

from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config
from scrapers.extract import extract_from_text, normalize_numeric_string


async def test_extract(ticker: str):
    from playwright.async_api import async_playwright
    url = f"https://valueinvesting.io/{ticker}/valuation/dcf-growth-exit-5y"
    print(f"\n--- Testing extract_from_text for {ticker} ({url}) ---")
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(user_agent=config.USER_AGENT)
        page = await ctx.new_page()
        try:
            await page.goto(url, timeout=30000, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)
            content = await page.content()

            print(f"Content Length: {len(content)}")
            for idx, pattern in enumerate(config.DCF_TEXT_REGEX_PATTERNS):
                match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
                if match:
                    group = match.group(1) if match.lastindex else match.group(0)
                    norm = normalize_numeric_string(group)
                    print(f"Pattern {idx} ({pattern!r}): raw_match={group!r} -> norm={norm!r}")
                else:
                    print(f"Pattern {idx} ({pattern!r}): NO MATCH")

            final_val = extract_from_text(content, config.DCF_TEXT_REGEX_PATTERNS)
            print(f"FINAL extract_from_text result: {final_val!r}")

        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(test_extract("AAPL"))
    asyncio.run(test_extract("MSFT"))
