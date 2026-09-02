import sys
import asyncio
import re
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config
from resilient_collector.proxy_pool import build_validated_pool
from resilient_collector.valueinvesting_session import ValueInvestingSession
from scrapers.extract import normalize_numeric_string

async def test_patterns(ticker="AAPL"):
    pool = await build_validated_pool()
    vi = ValueInvestingSession(pool)
    try:
        url = f"https://valueinvesting.io/{ticker}/valuation/dcf-growth-exit-5y"
        page = await vi.ensure_page()
        await page.goto(url, timeout=30000, wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)
        content = await page.content()
        
        # Test finditer with various regex patterns
        test_regexes = [
            r"The Discounted Cash Flow \(DCF\) (?:valuation|value) of [^.]*?is\s*([\d,]+\.?\d*)\s*USD",
            r"Discounted Cash Flow[^$\d\n]{0,80}\$?\s*([\d,]+\.?\d*)",
            r"Fair\s*Price[\s:]*\$?\s*([\d,]+\.?\d*)",
            r"Fair\s*Value[\s:]*\$?\s*([\d,]+\.?\d*)",
            r"Intrinsic\s*Value[\s:]*\$?\s*([\d,]+\.?\d*)",
            r"\"value_field\"\s*:\s*\"fair_price_5\"[^\}]*?\"value_numerical\"\s*:\s*\"([\d,]+\.?\d*)\"",
        ]
        
        print(f"=== Results for {ticker} ===")
        for r in test_regexes:
            for m in re.finditer(r, content, re.IGNORECASE | re.DOTALL):
                grp = m.group(1) if m.lastindex else m.group(0)
                norm = normalize_numeric_string(grp)
                if norm:
                    print(f"Pattern {r} -> Matched: {grp!r} -> Normalized: {norm}")
                    break
    finally:
        await vi.close()

if __name__ == "__main__":
    asyncio.run(test_patterns("AAPL"))
    asyncio.run(test_patterns("MSFT"))
