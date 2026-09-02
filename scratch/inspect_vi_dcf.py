import sys
import asyncio
import re
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config
from resilient_collector.proxy_pool import build_validated_pool
from resilient_collector.valueinvesting_session import ValueInvestingSession
from scrapers.extract import normalize_numeric_string

async def inspect_vi_html_dcf(ticker="AAPL"):
    pool = await build_validated_pool()
    vi = ValueInvestingSession(pool)
    try:
        url = f"https://valueinvesting.io/{ticker}/valuation/dcf"
        page = await vi.ensure_page()
        await page.goto(url, timeout=30000, wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)
        content = await page.content()
        
        print(f"--- URL: {url} --- Content length: {len(content)}")
        for idx, pattern in enumerate(config.DCF_TEXT_REGEX_PATTERNS):
            matches = list(re.finditer(pattern, content, re.IGNORECASE | re.DOTALL))
            print(f"\nPattern {idx} ({pattern}): {len(matches)} matches")
            for m in matches[:5]:
                group = m.group(1) if m.lastindex else m.group(0)
                norm = normalize_numeric_string(group)
                print(f"  Match: {m.group(0)!r} -> group: {group!r} -> norm: {norm!r}")
                # print context around match
                start = max(0, m.start() - 100)
                end = min(len(content), m.end() + 100)
                print(f"    Context: {content[start:end]!r}")
    finally:
        await vi.close()

if __name__ == "__main__":
    asyncio.run(inspect_vi_html_dcf("AAPL"))
    asyncio.run(inspect_vi_html_dcf("MSFT"))
