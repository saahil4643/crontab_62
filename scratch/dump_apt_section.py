from pathlib import Path
from bs4 import BeautifulSoup
import re

for ticker in ["aapl", "msft"]:
    html = Path(f"scratch/yahoo_{ticker}.html").read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    print(f"\n================ {ticker.upper()} ================")
    
    for h in soup.find_all(string=re.compile(r"Analyst Price Targets", re.IGNORECASE)):
        parent = h.find_parent("section") or h.find_parent("div", class_=re.compile(r"container|card|module|section|block|content", re.IGNORECASE)) or h.parent.parent
        print(f"--- Section for {ticker.upper()} ---")
        if parent:
            print("Parent Tag:", parent.name, parent.get("class"))
            print("Parent Text:\n", parent.get_text(" | ", strip=True)[:600])
            print("\nParent HTML snippet:\n", str(parent)[:1000])
        else:
            print("No parent container found.")
