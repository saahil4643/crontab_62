import sys
import re
import html
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scrapers.extract import normalize_numeric_string

for ticker in ["aapl", "msft"]:
    raw_html = Path(f"scratch/alphaspread_{ticker}.html").read_text(encoding="utf-8")
    unescaped = html.unescape(raw_html)
    
    # Snapshot search
    iv = re.search(r'"intrinsicValue"\s*:\s*\{\s*"base"\s*:\s*([\d.]+)', unescaped)
    dcf = re.search(r'"dcfValue"\s*:\s*\{\s*"base"\s*:\s*([\d.]+)', unescaped)
    
    print(f"\n{ticker.upper()}:")
    print(f"  Snapshot Intrinsic Value (Base): {normalize_numeric_string(iv.group(1)) if iv else None}")
    print(f"  Snapshot DCF Value (Base): {normalize_numeric_string(dcf.group(1)) if dcf else None}")
    
    # Headline search
    hl = re.search(r"The\s+<b[^>]*>intrinsic\s+value</b>\s+for[^<]*(?:<[^>]+>[^<]*)*?is\s+<span[^>]*>(?:<span[^>]*>)*([\d,]+\.?\d*)", raw_html, re.IGNORECASE)
    print(f"  Headline Intrinsic Value: {normalize_numeric_string(hl.group(1)) if hl else None}")
