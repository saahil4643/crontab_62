"""
scratch/debug_scrapers.py

Diagnostic script to inspect raw HTML content and network JSON payloads
from Alpha Spread, Value Investing, and GuruFocus for AAPL and MSFT.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config
from scrapers.extract import extract_from_json_payloads, extract_from_text, walk_json_for_value


async def debug_alphaspread(ticker: str = "AAPL"):
    from playwright.async_api import async_playwright
    url = f"https://www.alphaspread.com/security/nasdaq/{ticker.lower()}/summary"
    print(f"\n--- Debugging Alpha Spread: {url} ---", flush=True)
    json_payloads = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(user_agent=config.USER_AGENT)
        page = await ctx.new_page()

        async def _cap(resp):
            u = resp.url.lower()
            if any(h in u for h in config.JSON_URL_HINTS_ALPHASPREAD):
                try:
                    b = await resp.json()
                    json_payloads.append((u, b))
                except Exception:
                    pass

        page.on("response", _cap)
        try:
            res = await page.goto(url, timeout=30000, wait_until="domcontentloaded")
            print(f"Alpha Spread HTTP Status: {res.status if res else 'None'}", flush=True)
            await page.wait_for_timeout(3000)
            title = await page.title()
            print(f"Page Title: {title}", flush=True)
            content = await page.content()
            print(f"Content Length: {len(content)}", flush=True)

            if "just a moment" in title.lower() or "cf-browser-verification" in content.lower():
                print("BLOCKED BY CLOUDFLARE!", flush=True)

            # Check JSON payloads
            print(f"Captured {len(json_payloads)} JSON payloads", flush=True)
            for u, body in json_payloads:
                print(f"  JSON URL: {u}", flush=True)
                val = walk_json_for_value(body, config.DCF_JSON_KEY_HINTS)
                print(f"  Extracted from JSON: {val}", flush=True)

            # Regex text extraction test
            val_text = extract_from_text(content, config.DCF_TEXT_REGEX_PATTERNS)
            print(f"  Extracted from text: {val_text}", flush=True)

        finally:
            await browser.close()


async def debug_valueinvesting(ticker: str = "AAPL"):
    from playwright.async_api import async_playwright
    url = f"https://valueinvesting.io/{ticker}/valuation/dcf-growth-exit-5y"
    print(f"\n--- Debugging Value Investing: {url} ---", flush=True)
    json_payloads = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(user_agent=config.USER_AGENT)
        page = await ctx.new_page()

        async def _cap(resp):
            u = resp.url.lower()
            if any(h in u for h in config.JSON_URL_HINTS_VALUEINVESTING):
                try:
                    b = await resp.json()
                    json_payloads.append((u, b))
                except Exception:
                    pass

        page.on("response", _cap)
        try:
            res = await page.goto(url, timeout=30000, wait_until="domcontentloaded")
            print(f"ValueInvesting HTTP Status: {res.status if res else 'None'}", flush=True)
            await page.wait_for_timeout(3000)
            title = await page.title()
            print(f"Page Title: {title}", flush=True)
            content = await page.content()

            print(f"Captured {len(json_payloads)} JSON payloads", flush=True)
            for u, body in json_payloads:
                print(f"  JSON URL: {u}", flush=True)
                val = walk_json_for_value(body, config.DCF_JSON_KEY_HINTS)
                print(f"  walk_json_for_value result: {val}", flush=True)

            # Search text for 1000
            val_text = extract_from_text(content, config.DCF_TEXT_REGEX_PATTERNS)
            print(f"  Extracted from text: {val_text}", flush=True)

        finally:
            await browser.close()


async def debug_gurufocus(ticker: str = "AAPL"):
    from playwright.async_api import async_playwright
    url = f"https://www.gurufocus.com/stock/{ticker}/dcf?search={ticker}"
    print(f"\n--- Debugging GuruFocus: {url} ---", flush=True)
    json_payloads = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(user_agent=config.USER_AGENT)
        page = await ctx.new_page()

        async def _cap(resp):
            u = resp.url.lower()
            if "gurufocus" in u and ("dcf" in u or "valuation" in u or "term" in u):
                try:
                    b = await resp.json()
                    json_payloads.append((u, b))
                except Exception:
                    pass

        page.on("response", _cap)
        try:
            res = await page.goto(url, timeout=30000, wait_until="domcontentloaded")
            print(f"GuruFocus HTTP Status: {res.status if res else 'None'}", flush=True)
            await page.wait_for_timeout(3000)
            content = await page.content()

            print(f"Captured {len(json_payloads)} JSON payloads", flush=True)
            for u, body in json_payloads:
                print(f"  JSON URL: {u}", flush=True)
                val = walk_json_for_value(body, config.DCF_JSON_KEY_HINTS)
                print(f"  walk_json_for_value result: {val}", flush=True)

            val_text = extract_from_text(content, config.DCF_TEXT_REGEX_PATTERNS)
            print(f"  Extracted from text: {val_text}", flush=True)

        finally:
            await browser.close()


async def main():
    await debug_alphaspread("AAPL")
    await debug_valueinvesting("AAPL")
    await debug_gurufocus("AAPL")

if __name__ == "__main__":
    asyncio.run(main())
