import sys
import asyncio
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import config
from scrapers.extract import walk_json_for_value

async def dump_livewire(ticker="AAPL"):
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
        
        print(f"Captured {len(json_payloads)} JSON payloads for {ticker}")
        for u, b in json_payloads:
            # Let's see all keys and nested objects in b
            def find_numbers_and_keys(obj, path=""):
                if isinstance(obj, dict):
                    for k, v in obj.items():
                        new_path = f"{path}.{k}" if path else str(k)
                        if isinstance(v, (int, float)) and not isinstance(v, bool):
                            if v > 10 and v != 4193 and v != 4980 and v != 4152 and v != 4931:
                                print(f"  [NUM] {new_path} = {v}")
                        elif isinstance(v, str):
                            # check if string is a json snapshot
                            if v.startswith("{") and v.endswith("}"):
                                try:
                                    parsed = json.loads(v)
                                    find_numbers_and_keys(parsed, f"{new_path}(parsed)")
                                except:
                                    pass
                        find_numbers_and_keys(v, new_path)
                elif isinstance(obj, list):
                    for idx, item in enumerate(obj):
                        find_numbers_and_keys(item, f"{path}[{idx}]")
            find_numbers_and_keys(b)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(dump_livewire("AAPL"))
    asyncio.run(dump_livewire("MSFT"))
