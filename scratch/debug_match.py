import re
from pathlib import Path

content = Path("scratch/alphaspread_aapl.html").read_text(encoding="utf-8")
pat = r"The\s+<b[^>]*>(?:intrinsic|dcf)\s+value</b>\s+for.*?is\s+.*?([\d,]+\.?\d*)\s*<span[^>]*class=\"[^\"]*currency"
for m in re.finditer(pat, content, re.IGNORECASE | re.DOTALL):
    print("MATCH FULL:", m.group(0))
    print("CAPTURE:", m.group(1))
