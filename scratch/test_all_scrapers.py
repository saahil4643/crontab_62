import sys
import asyncio
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config
from models import ScrapeJob
from resilient_collector.proxy_pool import build_validated_pool
from resilient_collector.gurufocus_session import GuruFocusSession
from resilient_collector.valueinvesting_session import ValueInvestingSession
from resilient_collector.orchestrator import _scrape_alphaspread, _scrape_valueinvesting, _scrape_gurufocus

async def test_all():
    pool = await build_validated_pool()
    gf_session = GuruFocusSession(pool)
    vi_session = ValueInvestingSession(pool)
    
    tickers = ["AAPL", "MSFT"]
    results = {}
    
    try:
        # Alpha Spread
        for t in tickers:
            job = ScrapeJob(
                source="alphaspread",
                ticker=t,
                row=3 if t == "AAPL" else 4,
                value_col="D",
                value_col_index=4,
                label="Alpha Spread",
                security_type="nasdaq",
            )
            val = await _scrape_alphaspread(job, pool)
            results[f"alphaspread_{t}"] = val

        # Value Investing
        for t in tickers:
            job = ScrapeJob(
                source="valueinvesting",
                ticker=t,
                row=3 if t == "AAPL" else 4,
                value_col="I",
                value_col_index=9,
                label="ValueIo",
            )
            val = await _scrape_valueinvesting(job, vi_session)
            results[f"valueinvesting_{t}"] = val

        # GuruFocus
        for t in tickers:
            job = ScrapeJob(
                source="gurufocus",
                ticker=t,
                row=3 if t == "AAPL" else 4,
                value_col="O",
                value_col_index=15,
                label="GuruFocus",
            )
            val = await _scrape_gurufocus(job, gf_session)
            results[f"gurufocus_{t}"] = val

    finally:
        await gf_session.close()
        await vi_session.close()

    print("\n================== SCRAPER RESULTS ==================")
    for k, v in results.items():
        print(f"{k}: {v}")

if __name__ == "__main__":
    asyncio.run(test_all())
