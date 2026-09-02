import sys
import asyncio
import json
import re
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import config

async def check_livewire_details(ticker="AAPL"):
    from playwright.async_api import async_playwright
    url = f"https://www.alphaspread.com/security/nasdaq/{ticker.lower()}/summary"
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
        await page.wait_for_timeout(3500)
        
        for u, b in json_payloads:
            b_str = json.dumps(b)
            if "bearCaseData" in b_str or "base-case" in b_str or "dcf" in b_str.lower() or "intrinsic" in b_str.lower():
                print(f"URL: {u}")
                # print formatted json components
                if isinstance(b, dict) and "components" in b:
                    for comp in b["components"]:
                        snapshot = comp.get("snapshot")
                        if snapshot:
                            if isinstance(snapshot, str):
                                snap_obj = json.loads(snapshot)
                            else:
                                snap_obj = snapshot
                            print(f"Component data: {json.dumps(snap_obj.get('data', {}), indent=2)}")
                        effects = comp.get("effects", {})
                        if "html" in effects:
                            html = effects["html"]
                            # find prices/values in html
                            print(f"Effects html length: {len(html)}")
                            for match in re.finditer(r"\$\s*([\d,]+\.?\d*)", html):
                                print(f"  $ match in html: {match.group(0)}")
                            for match in re.finditer(r"([0-9]+\.[0-9]+)\s*USD", html):
                                print(f"  USD match in html: {match.group(0)}")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(check_livewire_details("AAPL"))
    asyncio.run(check_livewire_details("MSFT"))
