import sys
import re
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scrapers.extract import normalize_numeric_string

pat = r"The\s+<b[^>]*>(?:intrinsic|dcf)\s+value</b>\s+for.*?under\s+the\s+<span>Base\s+Case</span>\s+is\s+<span[^>]*><span[^>]*>([\d,]+\.?\d*)</span>\s*<span[^>]*class=\"[^\"]*currency"

for t in ["aapl", "msft"]:
    content = Path(f"scratch/alphaspread_{t}.html").read_text(encoding="utf-8")
    m = re.search(pat, content, re.IGNORECASE | re.DOTALL)
    print(f"{t.upper()} Match: {normalize_numeric_string(m.group(1)) if m else None}")
