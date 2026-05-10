import asyncio
import json
import re
from bs4 import BeautifulSoup

# -------------------------------
#  HTML helpers
# -------------------------------

def extract_og_image(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    tag = soup.find("meta", property="og:image")
    if tag and tag.get("content"):
        return tag["content"]
    return None

def extract_json(text: str):
    try:
        return json.loads(text)
    except Exception:
        return None

# -------------------------------
#  PUBLISHER-SPECIFIC PARSERS
# -------------------------------

def scrape_yen_press(html: str) -> str | None:
    # Next.js __NEXT_DATA__
    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>',
        html,
        re.DOTALL,
    )
    if not match:
        return extract_og_image(html)

    data = extract_json(match.group(1))
    if not data:
        return extract_og_image(html)

    try:
        queries = data["props"]["pageProps"]["dehydratedState"]["queries"]
        for q in queries:
            state = q.get("state", {})
            d = state.get("data", {})
            cover = d.get("cover")
            if cover:
                return cover
    except Exception:
        pass

    return extract_og_image(html)


def scrape_seven_seas(html: str) -> str | None:
    # Schema.org JSON
    soup = BeautifulSoup(html, "html.parser")
    ld = soup.find("script", type="application/ld+json")
    if ld and ld.string:
        data = extract_json(ld.string)
        if isinstance(data, dict) and "image" in data:
            return data["image"]

    return extract_og_image(html)


def scrape_jnovel(html: str) -> str | None:
    # Nuxt.js window.__NUXT__
    match = re.search(r"window\.__NUXT__\s*=\s*(\{.*?\});", html, re.DOTALL)
    if match:
        data = extract_json(match.group(1))
        if data:
            try:
                volumes = data["state"]["data"].get("volumes", [])
                for v in volumes:
                    if "cover" in v:
                        return v["cover"]
            except Exception:
                pass

    return extract_og_image(html)


def scrape_bookwalker(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    ld = soup.find("script", type="application/ld+json")
    if ld and ld.string:
        data = extract_json(ld.string)
        if isinstance(data, dict) and "image" in data:
            return data["image"]

    return extract_og_image(html)

# -------------------------------
#  PLAYWRIGHT SCRAPER
# -------------------------------

class CoverScraper:
    def __init__(self, context):
        self.context = context

    async def fetch_page(self, url: str) -> str | None:
        page = await self.context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(1500)  # allow hydration
            html = await page.content()
        except Exception:
            html = None
        finally:
            await page.close()
        return html

    async def get_cover(self, url: str) -> str | None:
        html = await self.fetch_page(url)
        if not html:
            return None

        if "yenpress.com" in url:
            return scrape_yen_press(html)
        if "sevenseasentertainment.com" in url:
            return scrape_seven_seas(html)
        if "j-novel.club" in url:
            return scrape_jnovel(html)
        if "bookwalker.com" in url:
            return scrape_bookwalker(html)

        return extract_og_image(html)
