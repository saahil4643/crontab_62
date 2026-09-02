import sys
import asyncio
import re
from pathlib import Path
from playwright.async_api import async_playwright
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import config
from scrapers.extract import extract_from_json_payloads, extract_from_text, walk_json_for_value

async def check_as(ticker="AAPL"):
    url = f"https://www.alphaspread.com/security/nasdaq/{ticker.lower()}/summary"
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(user_agent=config.USER_AGENT)
        page = await ctx.new_page()
        json_payloads = []
        async def _cap(resp):
            u = resp.url.lower()
            if any(h in u for h in config.JSON_URL_HINTS_ALPHASPREAD):
                try:
                    b = await resp.json()
                    json_payloads.append(b)
                except Exception:
                    pass
        page.on("response", _cap)
        await page.goto(url, timeout=30000, wait_until="domcontentloaded")
        await page.wait_for_timeout(3500)
        content = await page.content()
        print(f"--- Alpha Spread for {ticker} ---")
        print(f"JSON payloads: {len(json_payloads)}")
        val_json = extract_from_json_payloads(json_payloads, config.DCF_JSON_KEY_HINTS)
        print(f"extract_from_json_payloads: {val_json}")
        
        # Test each pattern against content
        for i, pat in enumerate(config.DCF_TEXT_REGEX_PATTERNS):
            matches = list(re.finditer(pat, content, re.IGNORECASE | re.DOTALL))
            print(f"Pattern {i} ({pat}): {len(matches)} matches")
            for m in matches[:3]:
                print(f"   Match: {m.group(0)!r} -> group(1)={m.group(1) if m.lastindex else 'none'}")
        
        val_text = extract_from_text(content, config.DCF_TEXT_REGEX_PATTERNS)
        print(f"extract_from_text: {val_text}")
        
        # Also check where Intrinsic Value or DCF Value is on the page
        for line in content.splitlines():
            if "intrinsic value" in line.lower() or "dcf" in line.lower() or "overvalued" in line.lower() or "undervalued" in line.lower():
                print(f"Line: {line.strip()[:200]}")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(check_as("AAPL"))
