from bs4 import BeautifulSoup
import re
from pathlib import Path

def analyze(ticker):
    p = Path(f"scratch/alphaspread_{ticker.lower()}.html")
    if not p.exists():
        print(f"File not found: {p}")
        return
    html = p.read_text(encoding="utf-8")
    print(f"\n==========================================")
    print(f"ANALYSIS OF SAVED HTML FOR: {ticker}")
    print(f"==========================================")
    
    # 1. Headline Intrinsic Value
    # Find all sentences mentioning intrinsic value / dcf
    soup = BeautifulSoup(html, "html.parser")
    
    # Check all wire:snapshot attributes in the DOM
    snapshots = soup.find_all(attrs={"wire:snapshot": True})
    print(f"Found {len(snapshots)} elements with wire:snapshot")
    for s in snapshots:
        val = s["wire:snapshot"]
        if "intrinsicValue" in val or "dcfValue" in val:
            print(f"  [wire:snapshot] Tag: {s.name} class={s.get('class')} id={s.get('id')}")
            # print snippet of snapshot
            print(f"     snapshot snippet: {val[:300]}")

    # Check visible text for Intrinsic Value / DCF Value
    for tag in soup.find_all(["div", "p", "span", "h1", "h2", "h3", "h4", "td", "th"]):
        txt = tag.get_text(" ", strip=True)
        if "intrinsic value" in txt.lower() and len(txt) < 150:
            # check parent
            if not tag.find(["div", "p"]):
                print(f"  [TEXT] <{tag.name} class='{tag.get('class')}'>: {txt}")

analyze("AAPL")
analyze("MSFT")
