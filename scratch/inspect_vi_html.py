"""
scratch/inspect_vi_html.py

Inspect full HTML content of ValueInvesting page for AAPL and MSFT.
"""

from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config
from scrapers.extract import extract_from_text


async def fetch_vi_html(ticker: str = "AAPL"):
    from playwright.async_api import async_playwright
    url = f"https://valueinvesting.io/{ticker}/valuation/dcf-growth-exit-5y"
    print(f"\n--- Fetching ValueInvesting HTML for {ticker} ---")
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(user_agent=config.USER_AGENT)
        page = await ctx.new_page()
        try:
            await page.goto(url, timeout=30000, wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)
            content = await page.content()
            print(f"Content Length: {len(content)}")

            # Search where 1000 appears in HTML text
            idx = 0
            while True:
                idx = content.find("1000", idx)
                if idx == -1:
                    break
                print(f"Found '1000' in HTML at index {idx}:")
                print(f"  Snippet: {content[max(0, idx-100):min(len(content), idx+100)]}")
                idx += 4

            # Test all regex patterns in config.DCF_TEXT_REGEX_PATTERNS
            print("\nTesting config.DCF_TEXT_REGEX_PATTERNS against HTML:")
            for i, p in enumerate(config.DCF_TEXT_REGEX_PATTERNS):
                m = re.search(p, content, re.IGNORECASE | re.DOTALL)
                if m:
                    g = m.group(1) if m.lastindex else m.group(0)
                    print(f"  Pattern {i} ({p!r}): match={g!r}")
                else:
                    print(f"  Pattern {i} ({p!r}): No match")

        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(fetch_vi_html("AAPL"))
