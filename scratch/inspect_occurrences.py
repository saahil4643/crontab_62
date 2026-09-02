import re
from pathlib import Path

content = Path("scratch/alphaspread_aapl.html").read_text(encoding="utf-8")
for m in re.finditer(r"The\s+<b[^>]*>(?:intrinsic|dcf)\s+value</b>", content, re.IGNORECASE):
    snippet = content[m.start():m.start()+400]
    print("--- OCCURRENCE ---")
    print(repr(snippet))
