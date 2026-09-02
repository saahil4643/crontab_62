import sys
import asyncio
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config
from models import ScrapeJob
from resilient_collector.proxy_pool import build_validated_pool
from resilient_collector.valueinvesting_session import ValueInvestingSession
from scrapers.extract import walk_json_for_value, _key_matches, _coerce_number, extract_from_text

async def debug_vi_1000(ticker="AAPL"):
    pool = await build_validated_pool()
    vi = ValueInvestingSession(pool)
    try:
        for path in config.VALUE_INVESTING_PATHS:
            url = config.VALUE_INVESTING_VALUATION_URL.format(ticker=ticker, path=path)
            json_payloads = []
            page = await vi.ensure_page()
            async def _cap(resp):
                u = resp.url.lower()
                if any(h in u for h in config.JSON_URL_HINTS_VALUEINVESTING):
                    try:
                        b = await resp.json()
                        json_payloads.append((u, b))
                    except:
                        pass
            page.on("response", _cap)
            await page.goto(url, timeout=30000, wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)
            content = await page.content()
            page.remove_listener("response", _cap)
            
            print(f"\n--- URL: {url} ---")
            print(f"Captured {len(json_payloads)} JSON payloads")
            for u, b in json_payloads:
                print(f"  URL: {u}")
                def walk_debug(obj, p=""):
                    if isinstance(obj, dict):
                        for k, v in obj.items():
                            cur = f"{p}.{k}" if p else k
                            if _key_matches(k, config.DCF_JSON_KEY_HINTS):
                                coerced = _coerce_number(v)
                                print(f"    MATCH key={cur} val={v!r} coerced={coerced!r}")
                            walk_debug(v, cur)
                    elif isinstance(obj, list):
                        for idx, item in enumerate(obj):
                            walk_debug(item, f"{p}[{idx}]")
                walk_debug(b)
            
            val_text = extract_from_text(content, config.DCF_TEXT_REGEX_PATTERNS)
            print(f"  extract_from_text: {val_text}")
    finally:
        await vi.close()

if __name__ == "__main__":
    asyncio.run(debug_vi_1000("AAPL"))
