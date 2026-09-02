import sys
import re
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scrapers.extract import normalize_numeric_string

def test_extraction(ticker):
    html = Path(f"scratch/alphaspread_{ticker.lower()}.html").read_text(encoding="utf-8")
    print(f"\n--- Testing Extraction for {ticker} ---")
    
    # 1. Test wire:snapshot extraction (cleanest & most precise)
    dcf_match = re.search(r'(?:&quot;|")dcfValue(?:&quot;|")\s*:\s*\{\s*(?:&quot;|")base(?:&quot;|")\s*:\s*([\d.]+)', html)
    iv_match = re.search(r'(?:&quot;|")intrinsicValue(?:&quot;|")\s*:\s*\{\s*(?:&quot;|")base(?:&quot;|")\s*:\s*([\d.]+)', html)
    
    if dcf_match:
        print(f"wire:snapshot DCF base: {normalize_numeric_string(dcf_match.group(1))}")
    if iv_match:
        print(f"wire:snapshot Intrinsic Value base: {normalize_numeric_string(iv_match.group(1))}")
        
    # 2. Test text regex extraction from headline
    headline_pat = r"The\s+<b[^>]*>intrinsic\s+value</b>\s+for[^<]*(?:<[^>]+>[^<]*)*?is\s+<span[^>]*>(?:<span[^>]*>)*([\d,]+\.?\d*)"
    m = re.search(headline_pat, html, re.IGNORECASE)
    if m:
        print(f"Headline regex match: {normalize_numeric_string(m.group(1))}")
    else:
        print("Headline regex match: None")

test_extraction("AAPL")
test_extraction("MSFT")
