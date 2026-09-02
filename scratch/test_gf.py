import sys
import asyncio
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config
from models import ScrapeJob
from resilient_collector.proxy_pool import build_validated_pool
from resilient_collector.gurufocus_session import GuruFocusSession
from resilient_collector.orchestrator import _scrape_gurufocus

async def test_gf():
    pool = await build_validated_pool()
    gf = GuruFocusSession(pool)
    try:
        job_aapl = ScrapeJob(
            source="gurufocus",
            ticker="AAPL",
            row=3,
            value_col="O",
            value_col_index=15,
            label="GuruFocus",
        )
        val_aapl = await _scrape_gurufocus(job_aapl, gf)
        print(f"GuruFocus AAPL result: {val_aapl}")

        job_msft = ScrapeJob(
            source="gurufocus",
            ticker="MSFT",
            row=4,
            value_col="O",
            value_col_index=15,
            label="GuruFocus",
        )
        val_msft = await _scrape_gurufocus(job_msft, gf)
        print(f"GuruFocus MSFT result: {val_msft}")
    finally:
        await gf.close()

if __name__ == "__main__":
    asyncio.run(test_gf())
