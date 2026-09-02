import asyncio
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from models import ScrapeJob
from resilient_collector.orchestrator import _scrape_alphaspread

async def trace_scrape():
    job_msft = ScrapeJob(row=4, ticker="MSFT", source="alphaspread", value_col="D", value_col_index=4, label="Alpha Spread", security_type="nasdaq")
    job_aapl = ScrapeJob(row=3, ticker="AAPL", source="alphaspread", value_col="D", value_col_index=4, label="Alpha Spread", security_type="nasdaq")
    
    print("Running _scrape_alphaspread for MSFT...")
    val_msft = await _scrape_alphaspread(job_msft, [])
    print(f"Result for MSFT: {val_msft}")
    
    print("\nRunning _scrape_alphaspread for AAPL...")
    val_aapl = await _scrape_alphaspread(job_aapl, [])
    print(f"Result for AAPL: {val_aapl}")

if __name__ == "__main__":
    asyncio.run(trace_scrape())
