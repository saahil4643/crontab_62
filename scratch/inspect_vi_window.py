import sys
import asyncio
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config
from resilient_collector.proxy_pool import build_validated_pool
from resilient_collector.valueinvesting_session import ValueInvestingSession

async def inspect_vi_window(ticker="AAPL"):
    pool = await build_validated_pool()
    vi = ValueInvestingSession(pool)
    try:
        url = f"https://valueinvesting.io/{ticker}/valuation/dcf-growth-exit-5y"
        page = await vi.ensure_page()
        await page.goto(url, timeout=30000, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        
        # Evaluate window variables in JS
        js_data = await page.evaluate("""() => {
            const result = {};
            for (let k in window) {
                if (k.startsWith('window.') || ['most', 'multiples', 'abs_upside', 'dcf', 'fair_value', 'intrinsic_value', 'valuation', 'data', 'company'].includes(k)) {
                    try {
                        result[k] = window[k];
                    } catch(e) {}
                }
            }
            // also look for fair value elements in DOM
            const fairValueEls = Array.from(document.querySelectorAll('*')).filter(el => el.textContent && (el.textContent.includes('Fair Value') || el.textContent.includes('Intrinsic Value') || el.textContent.includes('DCF Value')) && el.children.length < 3);
            result['elements'] = fairValueEls.map(el => ({tag: el.tagName, class: el.className, text: el.textContent.trim()})).slice(0, 10);
            return result;
        }""")
        print(f"--- JS DATA FOR {ticker} ---")
        print(f"window.most: {json.dumps(js_data.get('most'), indent=2)}")
        print(f"window.abs_upside: {js_data.get('abs_upside')}")
        print(f"DOM elements: {json.dumps(js_data.get('elements'), indent=2)}")
        
        # Also let's check all script tags in HTML
        content = await page.content()
        scripts = re.findall(r"<script[^>]*>(.*?)</script>", content, re.DOTALL)
        for idx, s in enumerate(scripts):
            if "window." in s or "fair" in s.lower() or "dcf" in s.lower():
                print(f"\nScript #{idx} (length {len(s)}):")
                lines = [l.strip() for l in s.splitlines() if l.strip()]
                for l in lines[:20]:
                    print(f"  {l[:150]}")
    finally:
        await vi.close()

if __name__ == "__main__":
    asyncio.run(inspect_vi_window("AAPL"))
    asyncio.run(inspect_vi_window("MSFT"))
