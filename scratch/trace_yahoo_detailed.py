import asyncio
import sys
import json
import re
from pathlib import Path
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config
from models import ScrapeJob
from resilient_collector.scheduler import YahooTickerGroup
from resilient_collector.orchestrator import _scrape_yahoo_group
from scrapers.extract import extract_from_json_payloads, extract_from_text, normalize_numeric_string

async def trace_yahoo_ticker(ticker: str):
    print(f"\n=======================================================")
    print(f"TRACING YAHOO FOR: {ticker}")
    print(f"=======================================================")
    
    # 1. Run the actual _scrape_yahoo_group function
    job_low = ScrapeJob(row=3, ticker=ticker, source="price_target_low", value_col="T", value_col_index=20, label="Price Target Low")
    job_avg = ScrapeJob(row=3, ticker=ticker, source="price_target_avg", value_col="U", value_col_index=21, label="Price Target Average")
    job_high = ScrapeJob(row=3, ticker=ticker, source="price_target_high", value_col="V", value_col_index=22, label="Price Target High")
    group = YahooTickerGroup(ticker=ticker, jobs=[job_low, job_avg, job_high])
    
    print(f"Running _scrape_yahoo_group({ticker})...")
    res = await _scrape_yahoo_group(group, [])
    print(f"Scraper returned: {res}")
    
    # 2. Detailed trace with Playwright
    url = config.YAHOO_QUOTE_URL.format(ticker=ticker)
    print(f"\nNavigating directly to: {url}")
    
    captured_responses = []
    
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(locale="en-US", user_agent=config.USER_AGENT)
        page = await ctx.new_page()

        async def _cap(response):
            u = response.url
            ct = response.headers.get("content-type", "")
            st = response.status
            captured_responses.append((u, st, ct))
            if "quotesummary" in u.lower() or "analyst" in u.lower() or "pricetarget" in u.lower() or "finance.yahoo.com/v" in u.lower():
                print(f"  [NETWORK MATCH] Status={st} URL={u[:120]} CT={ct}")
                try:
                    b = await response.json()
                    print(f"     JSON keys: {list(b.keys()) if isinstance(b, dict) else type(b)}")
                    # search for target in json
                    b_str = json.dumps(b)
                    for k in ["targetLowPrice", "targetMeanPrice", "targetHighPrice", "targetPrice", "target"]:
                        if k in b_str:
                            print(f"     -> FOUND KEY '{k}' in JSON response!")
                except Exception as e:
                    pass

        page.on("response", _cap)
        
        try:
            resp = await page.goto(url, timeout=30000, wait_until="domcontentloaded")
            print(f"Page response status: {resp.status if resp else 'None'}")
            print(f"Page final URL: {page.url}")
        except Exception as e:
            print(f"Page goto error: {e}")
            
        await page.wait_for_timeout(3000)
        content = await page.content()
        print(f"Page HTML content length: {len(content)}")
        
        # Check if consent / captcha / block
        if "consent.yahoo.com" in page.url or "guce.yahoo.com" in page.url:
            print("  [ALERT] Redirected to Yahoo Consent page!")
        if "captcha" in content.lower() or "robot" in content.lower() or "verify you are human" in content.lower():
            print("  [ALERT] Captcha or Bot verification detected in HTML!")
            
        # Search HTML for price targets
        print("\nSearching HTML for price target terms...")
        for pat in [
            r"targetLowPrice",
            r"targetMeanPrice",
            r"targetHighPrice",
            r"Price Target",
            r"Analyst Price Targets",
            r"Average Target",
            r"Low Target",
            r"High Target",
            r"Low.*?Average.*?High",
        ]:
            matches = list(re.finditer(pat, content, re.IGNORECASE))
            print(f"  Pattern '{pat}': {len(matches)} matches")
            
        # Let's search for embedded JSON in script tags
        for m in re.finditer(r'\{[^{}]*"targetMeanPrice"[^{}]*\}', content):
            print(f"  Found targetMeanPrice snippet in HTML: {m.group(0)}")
            
        for m in re.finditer(r'\{[^{}]*"targetLowPrice"[^{}]*\}', content):
            print(f"  Found targetLowPrice snippet in HTML: {m.group(0)}")

        for m in re.finditer(r'\{[^{}]*"targetHighPrice"[^{}]*\}', content):
            print(f"  Found targetHighPrice snippet in HTML: {m.group(0)}")
            
        # Save HTML for inspection
        out_file = ROOT / "scratch" / f"yahoo_{ticker.lower()}.html"
        out_file.write_text(content, encoding="utf-8")
        print(f"Saved HTML to {out_file}")
        
        await browser.close()

async def main():
    await trace_yahoo_ticker("AAPL")
    await trace_yahoo_ticker("MSFT")

if __name__ == "__main__":
    asyncio.run(main())
