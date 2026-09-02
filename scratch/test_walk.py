import sys
import asyncio
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import config
from scrapers.extract import walk_json_for_value, _key_matches, _coerce_number

async def test_walk(ticker="AAPL"):
    from playwright.async_api import async_playwright
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
                    json_payloads.append((u, b))
                except Exception:
                    pass
        page.on("response", _cap)
        await page.goto(url, timeout=30000, wait_until="domcontentloaded")
        await page.wait_for_timeout(3500)
        
        print(f"\nTesting walk_json_for_value for {ticker}: captured {len(json_payloads)}")
        for idx, (u, b) in enumerate(json_payloads):
            val = walk_json_for_value(b, config.DCF_JSON_KEY_HINTS)
            if val is not None:
                print(f"Payload #{idx} returned value: {val}")
            
            # Let's also check if snapshot has embedded JSON string:
            def check_snapshots(obj):
                if isinstance(obj, dict):
                    for k, v in obj.items():
                        if k == "snapshot" and isinstance(v, str):
                            try:
                                parsed = json.loads(v)
                                sval = walk_json_for_value(parsed, config.DCF_JSON_KEY_HINTS)
                                if sval is not None:
                                    print(f"  Embedded snapshot in payload #{idx} returned value: {sval}")
                            except:
                                pass
                        check_snapshots(v)
                elif isinstance(obj, list):
                    for item in obj:
                        check_snapshots(item)
            check_snapshots(b)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_walk("AAPL"))
    asyncio.run(test_walk("MSFT"))
