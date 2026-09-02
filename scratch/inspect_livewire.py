import sys
import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import config

async def inspect_alphaspread():
    url = "https://www.alphaspread.com/security/nasdaq/aapl/summary"
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(user_agent=config.USER_AGENT)
        page = await ctx.new_page()
        json_payloads = []

        async def _cap(resp):
            u = resp.url.lower()
            if "livewire" in u:
                try:
                    b = await resp.json()
                    json_payloads.append((u, b))
                except Exception:
                    pass

        page.on("response", _cap)
        await page.goto(url, timeout=30000, wait_until="domcontentloaded")
        await page.wait_for_timeout(4000)
        print(f"Captured {len(json_payloads)} livewire payloads")
        for idx, (u, b) in enumerate(json_payloads):
            b_str = json.dumps(b)
            # check if dcf or valuation or number is in payload
            if any(term in b_str.lower() for term in ["dcf", "valuation", "intrinsic", "fair", "257", "258", "259", "260", "200", "150"]):
                print(f"Payload #{idx} size={len(b_str)} keys={list(b.keys()) if isinstance(b, dict) else 'not dict'}")
                # print snippet
                print(f"Snippet: {b_str[:500]}")
                if "html" in b_str:
                    print("Found 'html' in payload!")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(inspect_alphaspread())
