import sys
import re
from bs4 import BeautifulSoup
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scrapers.extract import normalize_numeric_string

def extract_yahoo_targets_from_html(html: str) -> dict[str, str | None]:
    soup = BeautifulSoup(html, "html.parser")
    card = soup.find("section", attrs={"data-testid": "analyst-price-target-card"})
    
    results = {"price_target_low": None, "price_target_avg": None, "price_target_high": None}
    
    if card:
        # Check low
        low_el = card.find(class_=re.compile(r"\blow\b", re.I))
        if low_el:
            price_el = low_el.find(class_=re.compile(r"price", re.I)) or low_el
            results["price_target_low"] = normalize_numeric_string(price_el.get_text())
            
        # Check average
        avg_el = card.find(class_=re.compile(r"\baverage\b", re.I))
        if avg_el:
            price_el = avg_el.find(class_=re.compile(r"price", re.I)) or avg_el
            results["price_target_avg"] = normalize_numeric_string(price_el.get_text())
            
        # Check high
        high_el = card.find(class_=re.compile(r"\bhigh\b", re.I))
        if high_el:
            price_el = high_el.find(class_=re.compile(r"price", re.I)) or high_el
            results["price_target_high"] = normalize_numeric_string(price_el.get_text())
            
    # Also test pure Regex fallback on raw HTML
    # Matches: <span class="price...">215.00</span> <span>Low</span> or 215.00 | Low
    if not results["price_target_low"]:
        m = re.search(r"([\d,]+\.?\d*)\s*(?:<[^>]+>\s*)*Low\b", html, re.I)
        if m:
            results["price_target_low"] = normalize_numeric_string(m.group(1))

    if not results["price_target_avg"]:
        m = re.search(r"([\d,]+\.?\d*)\s*(?:<[^>]+>\s*)*Average\b", html, re.I)
        if m:
            results["price_target_avg"] = normalize_numeric_string(m.group(1))

    if not results["price_target_high"]:
        m = re.search(r"([\d,]+\.?\d*)\s*(?:<[^>]+>\s*)*High\b", html, re.I)
        if m:
            results["price_target_high"] = normalize_numeric_string(m.group(1))
            
    return results

for t in ["aapl", "msft"]:
    h = Path(f"scratch/yahoo_{t}.html").read_text(encoding="utf-8")
    res = extract_yahoo_targets_from_html(h)
    print(f"Extracted for {t.upper()}: {res}")
