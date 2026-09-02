from pathlib import Path
from bs4 import BeautifulSoup
import re
import json

html = Path("scratch/yahoo_aapl.html").read_text(encoding="utf-8")
print(f"HTML size: {len(html)}")

# 1. Search for any script tags with JSON / data
soup = BeautifulSoup(html, "html.parser")
scripts = soup.find_all("script")
print(f"Total script tags: {len(scripts)}")
for idx, s in enumerate(scripts):
    text = s.get_text()
    if "target" in text.lower() or "analyst" in text.lower() or "quoteSummary" in text.lower() or "financialData" in text.lower():
        print(f"  Script #{idx} (type={s.get('type')}, id={s.get('id')}) length={len(text)}")
        # search for target in this script
        for kw in ["targetLow", "targetMean", "targetHigh", "targetPrice", "target_price", "target_low", "target_mean", "target_high", "priceTarget"]:
            for m in re.finditer(kw, text, re.IGNORECASE):
                start = max(0, m.start() - 60)
                end = min(len(text), m.end() + 100)
                print(f"    Match for '{kw}': {repr(text[start:end])}")

# 2. Search visible text in DOM
for tag in soup.find_all(["div", "section", "table", "p", "span", "h1", "h2", "h3", "h4", "h5", "h6"]):
    t = tag.get_text(" ", strip=True)
    if "price target" in t.lower() or "analyst price" in t.lower() or "target price" in t.lower():
        if len(t) < 300 and not tag.find(["div", "section", "table"]):
            print(f"  DOM Element <{tag.name}>: {t}")
