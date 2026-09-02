import sys
import asyncio
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from models import ScrapeJob
from resilient_collector.proxy_pool import build_validated_pool
from resilient_collector.valueinvesting_session import ValueInvestingSession
from resilient_collector.orchestrator import _scrape_valueinvesting

async def test_vi():
    proxy_pool = await build_validated_pool()
    vi_session = ValueInvestingSession(proxy_pool)
    try:
        job_aapl = ScrapeJob(
            source="valueinvesting",
            ticker="AAPL",
            row=3,
            value_col="I",
            value_col_index=9,
            label="ValueIo",
        )
        val_aapl = await _scrape_valueinvesting(job_aapl, vi_session)
        print(f"ValueInvesting AAPL result: {val_aapl}")

        job_msft = ScrapeJob(
            source="valueinvesting",
            ticker="MSFT",
            row=4,
            value_col="I",
            value_col_index=9,
            label="ValueIo",
        )
        val_msft = await _scrape_valueinvesting(job_msft, vi_session)
        print(f"ValueInvesting MSFT result: {val_msft}")
    finally:
        await vi_session.close()

if __name__ == "__main__":
    asyncio.run(test_vi())
