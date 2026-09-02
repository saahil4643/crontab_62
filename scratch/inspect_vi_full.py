import sys
import asyncio
import re
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config
from resilient_collector.proxy_pool import build_validated_pool
from resilient_collector.valueinvesting_session import ValueInvestingSession

async def inspect_vi_full(ticker="AAPL"):
    pool = await build_validated_pool()
    vi = ValueInvestingSession(pool)
    try:
        url = f"https://valueinvesting.io/{ticker}/valuation/dcf-growth-exit-5y"
        page = await vi.ensure_page()
        await page.goto(url, timeout=30000, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        content = await page.content()
        print(f"--- {ticker} {url} ---")
        print(f"Content length: {len(content)}")
        
        # Look for fair value or DCF value or intrinsic value or share price
        lines = content.splitlines()
        for idx, l in enumerate(lines):
            if any(term in l.lower() for term in ["fair value", "intrinsic value", "dcf value", "upside", "downside", "target price", "growth exit"]):
                print(f"Line {idx}: {l.strip()[:200]}")
    finally:
        await vi.close()

if __name__ == "__main__":
    asyncio.run(inspect_vi_full("AAPL"))
    asyncio.run(inspect_vi_full("MSFT"))
