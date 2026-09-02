import asyncio
import sys
import json
import re
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config
from scrapers.extract import extract_from_json_payloads, extract_from_text, walk_json_for_value, _key_matches, _coerce_number
from playwright.async_api import async_playwright
from resilient_collector.nav_retry import goto_with_retry
from resilient_collector.proxy_pool import ProxyConfig

async def trace_ticker(ticker: str):
    url = config.ALPHA_SPREAD_URL.format(security_type="nasdaq", ticker=ticker.lower())
    print(f"\n=======================================================")
    print(f"DEEP DIVE: {ticker} on {url}")
    print(f"=======================================================")
    
    json_payloads = []
    
    async with async_playwright() as pw:
        proxy_cfg = ProxyConfig()
        launch_kwargs = {"headless": True}
        browser = await pw.chromium.launch(**launch_kwargs)
        ctx = await browser.new_context(user_agent=config.USER_AGENT)
        page = await ctx.new_page()

        async def _capture(response) -> None:
            try:
                u = response.url.lower()
                if any(h in u for h in config.JSON_URL_HINTS_ALPHASPREAD):
                    try:
                        body = await response.json()
                        json_payloads.append((response.url, body))
                    except Exception:
                        pass
            except Exception:
                pass

        page.on("response", _capture)

        await goto_with_retry(page, url, ticker=ticker, label="alphaspread", timeout_ms=30000)
        await page.wait_for_timeout(3500)
        content = await page.content()
        await page.close()
        await ctx.close()
        await browser.close()

    raw_payloads = [b for _, b in json_payloads]
    print(f"Captured {len(raw_payloads)} JSON payloads.")
    
    # 1. JSON Extraction Step
    print("\n--- 1. Testing JSON Payload Extraction ---")
    val_json = extract_from_json_payloads(raw_payloads, config.DCF_JSON_KEY_HINTS)
    print(f"extract_from_json_payloads returned: {val_json!r}")
    
    # Find which payload and which key matched
    for idx, (u, p) in enumerate(json_payloads):
        v = walk_json_for_value(p, config.DCF_JSON_KEY_HINTS)
        if v is not None:
            print(f"Payload #{idx} ({u[:80]}) returned: {v!r}")
            # Find the exact path
            def find_exact(obj, path=""):
                if isinstance(obj, dict):
                    for k, val in obj.items():
                        cur = f"{path}.{k}" if path else k
                        if isinstance(k, str) and _key_matches(k, config.DCF_JSON_KEY_HINTS):
                            c = _coerce_number(val)
                            print(f"   MATCH: {cur} = {val!r} -> coerced: {c}")
                        find_exact(val, cur)
                elif isinstance(obj, list):
                    for i, it in enumerate(obj):
                        find_exact(it, f"{path}[{i}]")
            find_exact(p)

    # 2. Text Extraction Step
    print("\n--- 2. Testing Text / Regex Extraction ---")
    val_text = extract_from_text(content, config.DCF_TEXT_REGEX_PATTERNS)
    print(f"extract_from_text returned: {val_text!r}")
    
    for i, pat in enumerate(config.DCF_TEXT_REGEX_PATTERNS):
        matches = list(re.finditer(pat, content, re.IGNORECASE | re.DOTALL))
        print(f"Pattern #{i} ({pat}): {len(matches)} matches")
        for m in matches[:5]:
            grp = m.group(1) if m.lastindex else m.group(0)
            norm = _coerce_number(grp)
            print(f"   Match: {m.group(0)!r} -> group(1): {grp!r} -> normalized: {norm!r}")

    # 3. What is the actual valuation on the page?
    print("\n--- 3. Actual Valuation in HTML / Snapshots ---")
    # Search for "intrinsic value" in content
    for m in re.finditer(r"The\s+<b[^>]*>intrinsic\s+value</b>\s+for.*?USD", content, re.IGNORECASE | re.DOTALL):
        print(f"Headline sentence: {m.group(0)!r}")

    for m in re.finditer(r"(&quot;intrinsicValue&quot;:\{[^}]+\})", content):
        print(f"Snapshot intrinsicValue: {m.group(0)}")
        
    for m in re.finditer(r"(&quot;dcfValue&quot;:\{[^}]+\})", content):
        print(f"Snapshot dcfValue: {m.group(0)}")

async def main():
    await trace_ticker("MSFT")
    await trace_ticker("AAPL")

if __name__ == "__main__":
    asyncio.run(main())
