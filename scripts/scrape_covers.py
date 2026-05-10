import asyncio
import json
import re
import time
from playwright.async_api import async_playwright

# polite delay between page loads
REQUEST_DELAY = 0.5

async def fetch_page(url):
    """Load the page in a real browser and return the full HTML."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/123.0 Safari/537.36"
        )
        page = await context.new_page()

        await page.goto(url, wait_until="networkidle")
        await asyncio.sleep(REQUEST_DELAY)

        html = await page.content()
        await browser.close()
        return html

def extract_og_image(html):
    match = re.search(r'<meta property="og:image" content="([^"]+)"', html)
    return match.group(1) if match else None

def extract_json(script_text):
    try:
        return json.loads(script_text)
    except Exception:
        return None

# -------------------------------
#  YEN PRESS (Next.js)
# -------------------------------
def scrape_yen_press(html):
    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>', html, re.DOTALL)
    if not match:
        return None

    data = extract_json(match.group(1))
    if not data:
        return None

    try:
        queries = data["props"]["pageProps"]["dehydratedState"]["queries"]
        for q in queries:
            cover = q["state"]["data"].get("cover")
            if cover:
                return cover
    except Exception:
        pass

    return extract_og_image(html)

# -------------------------------
#  SEVEN SEAS (Schema.org JSON)
# -------------------------------
def scrape_seven_seas(html):
    match = re.search(r'<script type="application/ld\+json">(.+?)</script>', html, re.DOTALL)
    if match:
        data = extract_json(match.group(1))
        if isinstance(data, dict) and "image" in data:
            return data["image"]

    return extract_og_image(html)

# -------------------------------
#  J-NOVEL CLUB (Nuxt.js)
# -------------------------------
def scrape_jnovel(html):
    match = re.search(r"window\.__NUXT__\s*=\s*(\{.*?\});", html, re.DOTALL)
    if match:
        data = extract_json(match.group(1))
        if not data:
            return None

        try:
            volumes = data["state"]["data"].get("volumes", [])
            for v in volumes:
                if "cover" in v:
                    return v["cover"]
        except Exception:
            pass

    return extract_og_image(html)

# -------------------------------
#  BOOKWALKER (Schema.org JSON)
# -------------------------------
def scrape_bookwalker(html):
    match = re.search(r'<script type="application/ld\+json">(.+?)</script>', html, re.DOTALL)
    if match:
        data = extract_json(match.group(1))
        if isinstance(data, dict) and "image" in data:
            return data["image"]

    return extract_og_image(html)

# -------------------------------
#  ROUTER
# -------------------------------
class CoverScraper:
    def __init__(self, browser):
        self.browser = browser

    async def fetch_page(self, url):
        page = await self.browser.new_page()
        await page.goto(url, wait_until="networkidle")
        await asyncio.sleep(0.5)  # polite delay
        html = await page.content()
        await page.close()
        return html

    async def get_cover(self, url):
        html = await self.fetch_page(url)

        if "yenpress.com" in url:
            return scrape_yen_press(html)
        if "sevenseasentertainment.com" in url:
            return scrape_seven_seas(html)
        if "j-novel.club" in url:
            return scrape_jnovel(html)
        if "bookwalker.com" in url:
            return scrape_bookwalker(html)

        return extract_og_image(html)