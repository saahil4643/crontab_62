import re
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scrapers.extract import normalize_numeric_string

# Pattern 1: Target the headline sentence cleanly
# "The <b ...>intrinsic value</b> for ... [under the ... Base Case ...] is <span ...>NUMBER</span> ... USD"
headline_pat = re.compile(
    r"The\s+<b[^>]*>(?:intrinsic|dcf)\s+value</b>\s+for\s+(?:<[^>]+>|[^<]){1,250}?\bis\s+(?:<[^>]+>\s*)*([\d,]+\.?\d*)\s*<span[^>]*class=\"[^\"]*currency",
    re.IGNORECASE | re.DOTALL,
)

# Pattern 2: Target the embedded wire:snapshot initial state
snapshot_pat = re.compile(
    r'(?:&quot;|")intrinsicValue(?:&quot;|")\s*:\s*\{\s*(?:&quot;|")base(?:&quot;|")\s*:\s*([\d.]+)',
    re.IGNORECASE,
)

for t in ["aapl", "msft"]:
    content = Path(f"scratch/alphaspread_{t}.html").read_text(encoding="utf-8")
    
    m_hl = headline_pat.search(content)
    m_snap = snapshot_pat.search(content)
    
    val_hl = normalize_numeric_string(m_hl.group(1)) if m_hl else None
    val_snap = normalize_numeric_string(m_snap.group(1)) if m_snap else None
    
    print(f"{t.upper()}:")
    print(f"  Headline: {val_hl}")
    print(f"  Snapshot: {val_snap}")
