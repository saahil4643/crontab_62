import sys
import asyncio
import json
import re
from pathlib import Path
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import config
from scrapers.extract import extract_from_json_payloads, extract_from_text

async def inspect_ticker(ticker: str):
    url = f"https://www.alphaspread.com/security/nasdaq/{ticker.lower()}/summary"
    print(f"\n=======================================================")
    print(f"FETCHING ALPHASPREAD PAGE FOR: {ticker}")
    print(f"URL: {url}")
    print(f"=======================================================")
    
    json_payloads = []
    
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(user_agent=config.USER_AGENT)
        page = await ctx.new_page()

        async def _on_response(resp):
            u = resp.url.lower()
            if any(h in u for h in config.JSON_URL_HINTS_ALPHASPREAD):
                try:
                    b = await resp.json()
                    json_payloads.append(b)
                except Exception:
                    pass

        page.on("response", _on_response)
        
        resp = await page.goto(url, timeout=30000, wait_until="domcontentloaded")
        print(f"1. Page goto status: {resp.status if resp else 'None'}")
        
        await page.wait_for_timeout(3500)
        content = await page.content()
        print(f"2. Page content length: {len(content)} chars")
        print(f"3. JSON payloads captured: {len(json_payloads)}")
        
        # Check extract_from_json_payloads
        json_val = extract_from_json_payloads(json_payloads, config.DCF_JSON_KEY_HINTS)
        print(f"4. extract_from_json_payloads result: {json_val!r}")
        
        # Check extract_from_text
        text_val = extract_from_text(content, config.DCF_TEXT_REGEX_PATTERNS)
        print(f"5. extract_from_text result: {text_val!r}")
        
        # Overall scraper result
        final_val = json_val if json_val is not None else text_val
        print(f"6. Final Alpha Spread Scraper Value: {final_val!r}")
        
        # Let's inspect regex patterns matches in detail
        print(f"\n--- Regex Pattern Matches for {ticker} ---")
        for i, pat in enumerate(config.DCF_TEXT_REGEX_PATTERNS):
            matches = list(re.finditer(pat, content, re.IGNORECASE | re.DOTALL))
            print(f"Pattern {i} [{pat}]: {len(matches)} matches")
            for m in matches[:5]:
                print(f"   Match: {m.group(0)!r} -> capture group 1: {m.group(1) if m.lastindex else 'None'}")
                
        # Find all occurrences of Intrinsic Value, DCF, Overvalued/Undervalued in the text
        print(f"\n--- Relevant Text Snippets in HTML for {ticker} ---")
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        for line in lines:
            if any(term in line.lower() for term in ["intrinsic value", "dcf value", "discounted cash flow", "overvalued", "undervalued", "fair price", "fair value"]):
                if len(line) < 300:
                    print(f"   Line: {line}")
                else:
                    print(f"   Line (truncated): {line[:200]} ... {line[-100:]}")
                    
        # Let's save the HTML to a scratch file so we can view it
        html_path = ROOT / "scratch" / f"alphaspread_{ticker.lower()}.html"
        html_path.write_text(content, encoding="utf-8")
        print(f"Saved full HTML to {html_path}")

        await browser.close()

async def main():
    await inspect_ticker("AAPL")
    await inspect_ticker("MSFT")

if __name__ == "__main__":
    asyncio.run(main())
