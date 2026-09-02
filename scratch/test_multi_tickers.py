import asyncio
import sys
import re
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import config
from scrapers.extract import normalize_numeric_string
from playwright.async_api import async_playwright
from resilient_collector.nav_retry import goto_with_retry

async def test_other_tickers():
    tickers = ["GOOGL", "NVDA", "TSLA"]
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(user_agent=config.USER_AGENT)
        page = await ctx.new_page()

        for t in tickers:
            url = f"https://www.alphaspread.com/security/nasdaq/{t.lower()}/summary"
            await goto_with_retry(page, url, ticker=t, label="alphaspread", timeout_ms=30000)
            await page.wait_for_timeout(2500)
            content = await page.content()
            
            # Test headline regex
            m = re.search(r"The\s+<b[^>]*>intrinsic\s+value</b>\s+for[^<]*(?:<[^>]+>[^<]*)*?is\s+<span[^>]*>(?:<span[^>]*>)*([\d,]+\.?\d*)", content, re.IGNORECASE)
            val = normalize_numeric_string(m.group(1)) if m else None
            print(f"Ticker: {t:5s} -> Extracted Intrinsic Value: {val}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_other_tickers())
