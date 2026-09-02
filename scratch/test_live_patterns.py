import asyncio
import sys
import re
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scrapers.extract import normalize_numeric_string
from playwright.async_api import async_playwright
import config
from resilient_collector.nav_retry import goto_with_retry

patterns = (
    r"The\s+<b[^>]*>(?:intrinsic|dcf)\s+value</b>\s+for.*?(?:under\s+the\s+<span>Base\s+Case</span>\s+)?is\s+<span[^>]*><span[^>]*>([\d,]+\.?\d*)</span>\s*<span[^>]*class=\"[^\"]*currency",
    r"The\s+<b[^>]*>(?:intrinsic|dcf)\s+value</b>\s+for.*?is\s+(?:<[^>]+>\s*)*([\d,]+\.?\d*)</span>\s*<span[^>]*class=\"[^\"]*currency",
)

async def test_live():
    tickers = ["AAPL", "MSFT", "GOOGL", "NVDA", "TSLA"]
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(user_agent=config.USER_AGENT)
        page = await ctx.new_page()
        for t in tickers:
            url = f"https://www.alphaspread.com/security/nasdaq/{t.lower()}/summary"
            await goto_with_retry(page, url, ticker=t, label="alphaspread", timeout_ms=30000)
            await page.wait_for_timeout(3000)
            content = await page.content()
            val = None
            for p in patterns:
                m = re.search(p, content, re.IGNORECASE | re.DOTALL)
                if m:
                    val = normalize_numeric_string(m.group(1))
                    break
            print(f"{t:5s} -> {val}")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_live())
