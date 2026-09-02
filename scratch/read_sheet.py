import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import gspread
from setup_test_sheet import get_client, get_sheet_id, WORKSHEET_NAME

def read_sheet():
    client, _ = get_client()
    sheet_id = "1qBFvnlgWg5YCk_IFMpC5Nf4vYxKvhXBvSZ2ErWqScjk"
    ss = client.open_by_key(sheet_id)
    ws = ss.worksheet(WORKSHEET_NAME)
    all_values = ws.get_all_values()
    for row_idx, row in enumerate(all_values[:6], start=1):
        print(f"Row {row_idx}: {row}")

if __name__ == "__main__":
    read_sheet()
