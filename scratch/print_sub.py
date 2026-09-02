from pathlib import Path
import re

content = Path("scratch/alphaspread_aapl.html").read_text(encoding="utf-8")
idx = content.find('The <b class="space-no-wrap">intrinsic value</b> for')
print(repr(content[idx:idx+350]))
