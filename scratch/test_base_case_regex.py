import re
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scrapers.extract import normalize_numeric_string

headline_pat = r"The\s+<b[^>]*>(?:intrinsic|dcf)\s+value</b>\s+for\s+(?:<[^>]+>)*\s*[^<]+(?:\s*<[^>]+>)*\s*under\s+the\s+<span>Base\s+Case</span>\s+is\s+(?:<[^>]+>)*([\d,]+\.?\d*)\s*<span"

for t in ["aapl", "msft"]:
    content = Path(f"scratch/alphaspread_{t}.html").read_text(encoding="utf-8")
    m = re.search(headline_pat, content, re.IGNORECASE)
    if m:
        print(f"{t.upper()} CAPTURE: {normalize_numeric_string(m.group(1))}")
    else:
        print(f"{t.upper()} NO MATCH")
