#!/usr/bin/env python3
"""
Cron 62 - Test Google Sheet setup utility.

Usage:
    python setup_test_sheet.py YOUR_SHEET_ID

The script reuses the Google service-account credentials expected by Cron 62.
It creates/updates only the "Missing Value" worksheet and prepares a small
test dataset for Alpha Spread, Value Investing, and GuruFocus.

It does NOT run Cron 62 or modify scraper/orchestrator code.
"""

import os
import sys
from pathlib import Path

try:
    import gspread
    from google.oauth2.service_account import Credentials
except ImportError as exc:
    raise SystemExit(
        "Missing dependency. Install the project's existing Google Sheets "
        "dependencies (for example: pip install gspread google-auth)."
    ) from exc


WORKSHEET_NAME = "Missing Value"

# Columns A-V. Only the cells below are populated.
HEADERS = {
    "B1": "ALPHASPREAD",
    "G1": "VALUEINVESTING",
    "M1": "GURUFOCUS",
    "R1": "YAHOO TARGETS",

    "B2": "Index",
    "C2": "Ticker",
    "D2": "DCF",

    "G2": "Index",
    "H2": "Ticker",
    "I2": "DCF",

    "M2": "Index",
    "N2": "Ticker",
    "O2": "DCF",

    "R2": "Index",
    "S2": "Ticker",
    "T2": "Low Target",
    "U2": "Avg Target",
    "V2": "High Target",
}

TEST_TICKERS = ["AAPL", "MSFT"]


def find_credentials():
    """Find the same common service-account credential locations used by the project."""
    candidates = []

    env_path = os.getenv("GOOGLE_CREDENTIALS_PATH")
    if env_path:
        candidates.append(Path(env_path))

    project_root = Path(__file__).resolve().parent.parent
    candidates.extend([
        project_root / "keys.json",
        Path.cwd() / "keys.json",
    ])

    for path in candidates:
        if path.exists():
            return path

    raise FileNotFoundError(
        "Could not find Google service-account credentials. "
        "Set GOOGLE_CREDENTIALS_PATH or place keys.json in the project root."
    )


def get_client():
    credentials_path = find_credentials()

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    credentials = Credentials.from_service_account_file(
        str(credentials_path),
        scopes=scopes,
    )
    return gspread.authorize(credentials), credentials_path


def get_sheet_id():
    if len(sys.argv) >= 2:
        return sys.argv[1].strip()

    sheet_id = os.getenv("SHEET_ID", "").strip()
    if sheet_id:
        return sheet_id

    raise SystemExit(
        "Usage: python setup_test_sheet.py YOUR_SHEET_ID\n"
        "or set SHEET_ID in the environment."
    )


def prepare_worksheet(spreadsheet):
    try:
        worksheet = spreadsheet.worksheet(WORKSHEET_NAME)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(
            title=WORKSHEET_NAME,
            rows=100,
            cols=22,
        )

    # Prepare the expected headers.
    worksheet.batch_update([
        {"range": cell, "values": [[value]]}
        for cell, value in HEADERS.items()
    ])

    # Test rows: AAPL and MSFT in the three DCF source blocks and Yahoo section.
    rows = []
    for row_number, ticker in enumerate(TEST_TICKERS, start=3):
        rows.extend([
            {"range": f"B{row_number}:D{row_number}",
             "values": [["Nasdaq", ticker, ""]]},
            {"range": f"G{row_number}:I{row_number}",
             "values": [["Nasdaq", ticker, ""]]},
            {"range": f"M{row_number}:O{row_number}",
             "values": [["Nasdaq", ticker, ""]]},
            {"range": f"R{row_number}:V{row_number}",
             "values": [["Nasdaq", ticker, "", "", ""]]},
        ])

    worksheet.batch_update(rows)

    return worksheet


def main():
    sheet_id = get_sheet_id()
    client, credentials_path = get_client()

    try:
        spreadsheet = client.open_by_key(sheet_id)
    except Exception as exc:
        raise SystemExit(
            f"Could not open spreadsheet.\n"
            f"Check the SHEET_ID and make sure the sheet is shared with the "
            f"service-account email from {credentials_path}.\n\n{exc}"
        ) from exc

    worksheet = prepare_worksheet(spreadsheet)

    print("\nTest Google Sheet setup complete.")
    print(f"Spreadsheet: {spreadsheet.title}")
    print(f"Worksheet:   {worksheet.title}")
    print("Test tickers: AAPL, MSFT")
    print("")
    print("DCF input columns:")
    print("  Alpha Spread:     C")
    print("  Value Investing:  H")
    print("  GuruFocus:        N")
    print("")
    print("DCF output columns:")
    print("  Alpha Spread:     D")
    print("  Value Investing:  I")
    print("  GuruFocus:        O")
    print("")
    print("The script did not run Cron 62 and did not modify its code.")


if __name__ == "__main__":
    main()
