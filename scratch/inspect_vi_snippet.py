import sys
import asyncio
import re
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config
from resilient_collector.proxy_pool import build_validated_pool
from resilient_collector.valueinvesting_session import ValueInvestingSession

async def inspect_vi_html_snippet(ticker="AAPL"):
    pool = await build_validated_pool()
    vi = ValueInvestingSession(pool)
    try:
        url = f"https://valueinvesting.io/{ticker}/valuation/dcf-growth-exit-5y"
        page = await vi.ensure_page()
        await page.goto(url, timeout=30000, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        content = await page.content()
        
        for num_str in ["204.37", "430", "400", "500", "USD"]:
            idx = 0
            while True:
                idx = content.find("204.37", idx)
                if idx == -1:
                    break
                print(f"Found '204.37' at {idx}:")
                print(f"  {content[max(0, idx-150):min(len(content), idx+150)]!r}\n")
                idx += 6
                
    finally:
        await vi.close()

if __name__ == "__main__":
    asyncio.run(inspect_vi_html_snippet("AAPL"))
