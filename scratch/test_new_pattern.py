import re
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scrapers.extract import normalize_numeric_string, extract_from_text

patterns = (
    r"The\s+<b[^>]*>(?:intrinsic|dcf)\s+value</b>\s+for.*?is\s+.*?([\d,]+\.?\d*)\s*<span[^>]*class=\"[^\"]*currency",
    r"The Discounted Cash Flow \(DCF\) (?:valuation|value) of [^.]*?is\s*([\d,]+\.?\d*)\s*USD",
    r"Discounted Cash Flow[^$\d\n]{0,80}\$?\s*([\d,]+\.?\d*)",
    r"DCF\s*(?:Value)?[\s:]*\$?\s*([\d,]+\.?\d*)",
    r"Fair\s*Value[\s:]*\$?\s*([\d,]+\.?\d*)",
    r"Fair\s*Price[\s:]*\$?\s*([\d,]+\.?\d*)",
    r"Intrinsic\s*Value[\s:]*\$?\s*([\d,]+\.?\d*)",
)

for t in ["aapl", "msft"]:
    f = Path(f"scratch/alphaspread_{t}.html")
    if f.exists():
        content = f.read_text(encoding="utf-8")
        res = extract_from_text(content, patterns)
        print(f"{t.upper()} extracted: {res}")
