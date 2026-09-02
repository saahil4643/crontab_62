import asyncio
import sys
import re
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config
from scrapers.extract import extract_from_text
from playwright.async_api import async_playwright
from resilient_collector.nav_retry import goto_with_retry

PRICE_TARGET_TEXT_REGEX: dict[str, tuple[str, ...]] = {
    "low": (
        r"<div[^>]*class=\"[^\"]*\blow\b[^\"]*\".*?<span[^>]*class=\"[^\"]*\bprice\b[^\"]*\">([\d,]+\.?\d*)</span>",
        r"<span[^>]*class=\"[^\"]*\bprice\b[^\"]*\">([\d,]+\.?\d*)</span>\s*<span[^>]*>\s*Low\s*</span>",
    ),
    "avg": (
        r"<div[^>]*class=\"[^\"]*\baverage\b[^\"]*\".*?<span[^>]*class=\"[^\"]*\bprice\b[^\"]*\">([\d,]+\.?\d*)</span>",
        r"<span[^>]*class=\"[^\"]*\bprice\b[^\"]*\">([\d,]+\.?\d*)</span>\s*<span[^>]*>\s*Average\s*</span>",
    ),
    "high": (
        r"<div[^>]*class=\"[^\"]*\bhigh\b[^\"]*\".*?<span[^>]*class=\"[^\"]*\bprice\b[^\"]*\">([\d,]+\.?\d*)</span>",
        r"<span[^>]*class=\"[^\"]*\bprice\b[^\"]*\">([\d,]+\.?\d*)</span>\s*<span[^>]*>\s*High\s*</span>",
    ),
}

async def test_yahoo_tickers():
    tickers = ["GOOGL", "NVDA", "TSLA"]
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(locale="en-US", user_agent=config.USER_AGENT)
        page = await ctx.new_page()
        
        for t in tickers:
            url = config.YAHOO_QUOTE_URL.format(ticker=t)
            await goto_with_retry(page, url, ticker=t, label="yahoo", timeout_ms=30000)
            await page.wait_for_timeout(2000)
            content = await page.content()
            
            low = extract_from_text(content, PRICE_TARGET_TEXT_REGEX["low"])
            avg = extract_from_text(content, PRICE_TARGET_TEXT_REGEX["avg"])
            high = extract_from_text(content, PRICE_TARGET_TEXT_REGEX["high"])
            print(f"{t:5s} -> Low: {low}, Avg: {avg}, High: {high}")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_yahoo_tickers())
