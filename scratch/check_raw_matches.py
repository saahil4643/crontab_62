import re
import html
from pathlib import Path

raw = Path("scratch/alphaspread_aapl.html").read_text(encoding="utf-8")
for m in re.finditer(r"intrinsicValue|dcfValue", raw):
    start = max(0, m.start() - 50)
    end = min(len(raw), m.end() + 100)
    print("MATCH:", raw[start:end])
