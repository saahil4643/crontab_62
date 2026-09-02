import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sheet_client import DcfSheetClient

client = DcfSheetClient()
values = client.worksheet.get_all_values()
print(f"Total rows in sheet: {len(values)}")
for idx, r in enumerate(values[:10]):
    print(f"Row {idx+1}: {r}")

jobs = client.collect_jobs()
print(f"\nTotal jobs collected: {len(jobs)}")
for j in jobs:
    print(f"  Job: row={j.row} ticker={j.ticker} source={j.source} col={j.value_col} label={j.label}")
