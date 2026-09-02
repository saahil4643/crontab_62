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

async def debug_tickers():
    tickers = ["NVDA", "TSLA", "GOOGL", "AAPL", "MSFT"]
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(user_agent=config.USER_AGENT)
        
        for t in tickers:
            page = await ctx.new_page()
            url = f"https://www.alphaspread.com/security/nasdaq/{t.lower()}/summary"
            await goto_with_retry(page, url, ticker=t, label="alphaspread", timeout_ms=30000)
            await page.wait_for_timeout(3500)
            content = await page.content()
            
            # Find any sentence starting with "The" and containing "intrinsic value" or "dcf value"
            print(f"\n==================== {t} ====================")
            for m in re.finditer(r"The\s+<b[^>]*>(?:intrinsic|dcf)\s+value</b>[^.]*?USD", content, re.IGNORECASE | re.DOTALL):
                clean = re.sub(r"\s+", " ", m.group(0))
                print(f"Matched sentence HTML: {clean}")
            
            # Test flexible pattern:
            # Matches: The <b...>intrinsic value</b> ... is ... <span...>NUMBER</span> USD
            flex_pat = r"The\s+<b[^>]*>(?:intrinsic|dcf)\s+value</b>\s+for.*?is\s+.*?([\d,]+\.?\d*)\s*<span[^>]*class=\"[^\"]*currency"
            m2 = re.search(flex_pat, content, re.IGNORECASE | re.DOTALL)
            if m2:
                print(f"Flex regex extracted: {normalize_numeric_string(m2.group(1))}")
            else:
                # Check why it didn't match
                for line in content.splitlines():
                    if "intrinsic value" in line.lower() and "is" in line.lower() and "usd" in line.lower():
                        print(f"Candidate line: {line.strip()[:250]}")
            
            await page.close()

        await browser.close()

if __name__ == "__main__":
    asyncio.run(debug_tickers())
