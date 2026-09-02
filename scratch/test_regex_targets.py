import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scrapers.extract import extract_from_text

PRICE_TARGET_TEXT_REGEX: dict[str, tuple[str, ...]] = {
    "low": (
        r"<div[^>]*class=\"[^\"]*\blow\b[^\"]*\".*?<span[^>]*class=\"[^\"]*\bprice\b[^\"]*\">([\d,]+\.?\d*)</span>",
        r"<span[^>]*class=\"[^\"]*\bprice\b[^\"]*\">([\d,]+\.?\d*)</span>\s*<span[^>]*>\s*Low\s*</span>",
        r"([\d,]+\.?\d*)\s*\|\s*Low\b",
        r"Price\s*Target\s*Low[\s:]*\$?\s*([\d,]+\.?\d*)",
        r"Low[\s:]*\$?\s*([\d,]+\.?\d*)",
    ),
    "avg": (
        r"<div[^>]*class=\"[^\"]*\baverage\b[^\"]*\".*?<span[^>]*class=\"[^\"]*\bprice\b[^\"]*\">([\d,]+\.?\d*)</span>",
        r"<span[^>]*class=\"[^\"]*\bprice\b[^\"]*\">([\d,]+\.?\d*)</span>\s*<span[^>]*>\s*Average\s*</span>",
        r"([\d,]+\.?\d*)\s*\|\s*Average\b",
        r"Price\s*Target\s*(?:Average|Mean)?[\s:]*\$?\s*([\d,]+\.?\d*)",
        r"Average\s*Target[\s:]*\$?\s*([\d,]+\.?\d*)",
        r"Consensus[\s:]*\$?\s*([\d,]+\.?\d*)",
    ),
    "high": (
        r"<div[^>]*class=\"[^\"]*\bhigh\b[^\"]*\".*?<span[^>]*class=\"[^\"]*\bprice\b[^\"]*\">([\d,]+\.?\d*)</span>",
        r"<span[^>]*class=\"[^\"]*\bprice\b[^\"]*\">([\d,]+\.?\d*)</span>\s*<span[^>]*>\s*High\s*</span>",
        r"([\d,]+\.?\d*)\s*\|\s*High\b",
        r"Price\s*Target\s*High[\s:]*\$?\s*([\d,]+\.?\d*)",
        r"High[\s:]*\$?\s*([\d,]+\.?\d*)",
    ),
}

for t in ["aapl", "msft"]:
    h = Path(f"scratch/yahoo_{t}.html").read_text(encoding="utf-8")
    low = extract_from_text(h, PRICE_TARGET_TEXT_REGEX["low"])
    avg = extract_from_text(h, PRICE_TARGET_TEXT_REGEX["avg"])
    high = extract_from_text(h, PRICE_TARGET_TEXT_REGEX["high"])
    print(f"{t.upper()} -> Low: {low}, Avg: {avg}, High: {high}")
