import sys
import asyncio
import json
import re
from pathlib import Path
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import config
from scrapers.extract import extract_from_json_payloads, extract_from_text, walk_json_for_value, _key_matches, _coerce_number

async def diagnose_ticker(ticker: str):
    print(f"\n==========================================")
    print(f"DIAGNOSING ALPHASPREAD FOR: {ticker}")
    print(f"==========================================")
    url = f"https://www.alphaspread.com/security/nasdaq/{ticker.lower()}/summary"
    
    json_payloads = []
    responses = []
    
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(user_agent=config.USER_AGENT)
        page = await ctx.new_page()

        async def _on_response(resp):
            u = resp.url
            status = resp.status
            content_type = resp.headers.get("content-type", "")
            responses.append((u, status, content_type))
            if any(h in u.lower() for h in config.JSON_URL_HINTS_ALPHASPREAD):
                try:
                    b = await resp.json()
                    json_payloads.append((u, b))
                except Exception as e:
                    pass

        page.on("response", _on_response)
        
        print(f"1. Navigating to {url}...")
        try:
            resp = await page.goto(url, timeout=30000, wait_until="domcontentloaded")
            print(f"   Page goto completed. HTTP status: {resp.status if resp else 'None'}")
        except Exception as e:
            print(f"   Page goto ERROR: {e}")
            await browser.close()
            return
            
        print(f"2. Waiting 3.5s for dynamic content & Livewire...")
        await page.wait_for_timeout(3500)
        
        content = await page.content()
        print(f"   Page HTML content length: {len(content)}")
        
        # Check Livewire responses
        print(f"3. Network responses captured total: {len(responses)}")
        print(f"   Matching JSON/Livewire responses captured: {len(json_payloads)}")
        for idx, (u, b) in enumerate(json_payloads):
            print(f"   [JSON #{idx}] URL: {u[:100]} | Type: {type(b)}")
            if isinstance(b, dict):
                print(f"      Keys: {list(b.keys())}")
                if "components" in b:
                    for c_idx, comp in enumerate(b["components"]):
                        if isinstance(comp, dict):
                            print(f"      Component[{c_idx}] keys: {list(comp.keys())}")
                            if "snapshot" in comp:
                                try:
                                    snap = json.loads(comp["snapshot"])
                                    print(f"         snapshot.data keys: {list(snap.get('data', {}).keys())}")
                                    if "dcf" in str(snap).lower() or "valuation" in str(snap).lower():
                                        print(f"         found dcf/val in snapshot: {str(snap)[:200]}")
                                except:
                                    pass

        # 4. Check extract_from_json_payloads
        raw_payloads = [b for _, b in json_payloads]
        val_from_json = extract_from_json_payloads(raw_payloads, config.DCF_JSON_KEY_HINTS)
        print(f"4. extract_from_json_payloads returned: {val_from_json!r}")
        
        # Detailed walkthrough of why walk_json_for_value found or didn't find anything
        def debug_walk(obj, path=""):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    curr = f"{path}.{k}" if path else str(k)
                    if isinstance(k, str) and _key_matches(k, config.DCF_JSON_KEY_HINTS):
                        coerced = _coerce_number(v)
                        print(f"   -> MATCHED KEY: {curr} = {v!r} (type={type(v)}) -> coerced: {coerced}")
                    debug_walk(v, curr)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    debug_walk(item, f"{path}[{i}]")
        
        print("   Debugging walk_json_for_value matches in payloads:")
        for idx, p in enumerate(raw_payloads):
            debug_walk(p, f"payload[{idx}]")

        # 5. Check regex extraction on HTML content
        print("5. Checking regex patterns against HTML content:")
        for idx, pat in enumerate(config.DCF_TEXT_REGEX_PATTERNS):
            matches = list(re.finditer(pat, content, re.IGNORECASE | re.DOTALL))
            print(f"   Pattern [{idx}] {pat!r} -> {len(matches)} matches")
            for m in matches[:3]:
                print(f"      Found: {m.group(0)!r} -> capture group(1)={m.group(1) if m.lastindex else 'N/A'}")
        
        val_from_text = extract_from_text(content, config.DCF_TEXT_REGEX_PATTERNS)
        print(f"   extract_from_text returned: {val_from_text!r}")

        # 6. Look for DCF / Intrinsic Value in HTML
        print("6. Searching HTML for Intrinsic Value / DCF text:")
        for line in content.splitlines():
            l_lower = line.lower()
            if "dcf" in l_lower or "intrinsic" in l_lower or "undervalued" in l_lower or "overvalued" in l_lower:
                clean_l = " ".join(line.split())
                if len(clean_l) > 200:
                    clean_l = clean_l[:200] + "..."
                print(f"   HTML Line: {clean_l}")

        await browser.close()

async def main():
    await diagnose_ticker("MSFT")
    await diagnose_ticker("AAPL")

if __name__ == "__main__":
    asyncio.run(main())
