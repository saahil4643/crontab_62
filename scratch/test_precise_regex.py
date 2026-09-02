import re
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scrapers.extract import normalize_numeric_string, extract_from_text

pattern = r"The\s+<b[^>]*>(?:intrinsic|dcf)\s+value</b>\s+for.*?is\s+(?:<[^>]+>\s*)*([\d,]+\.?\d*)\s*<span[^>]*class=\"[^\"]*currency"

for t in ["aapl", "msft"]:
    f = Path(f"scratch/alphaspread_{t}.html")
    if f.exists():
        content = f.read_text(encoding="utf-8")
        m = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
        if m:
            print(f"{t.upper()} CAPTURE: {normalize_numeric_string(m.group(1))}")
        else:
            print(f"{t.upper()} NO MATCH")
