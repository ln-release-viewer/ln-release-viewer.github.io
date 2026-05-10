import asyncio
import json
import re
from bs4 import BeautifulSoup
import re
import hashlib

def _debug_slug(url: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9-]", "-", url.lower())
    h = hashlib.sha1(url.encode("utf-8")).hexdigest()[:6]
    return f"{safe[:40]}-{h}"


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
        html = None

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)

            # --- Hydration waits (important for Yen Press) ---
            # Wait for Next.js hydration to finish
            try:
                await page.wait_for_function(
                    "() => window.__NEXT_DATA__ && window.__NEXT_DATA__.props",
                    timeout=5000
                )
            except:
                pass

            # Wait for any image that looks like a cover
            try:
                await page.wait_for_selector("img[src*='cover']", timeout=5000)
            except:
                pass

            # Give JS a little more time (Yen Press sometimes needs this)
            await page.wait_for_timeout(1000)

            html = await page.content()

            # --- Cloudflare detection ---
            if html and (
                "cf-browser-verification" in html
                or "Checking your browser" in html
                or "cf-challenge" in html
            ):
                print(f"⚠ Cloudflare challenge detected for: {url}")

                # Dump HTML for debugging
                debug_path = f"debug_cloudflare_{slugify_short(url, '')}.html"
                with open(debug_path, "w", encoding="utf-8") as f:
                    f.write(html)
                print(f"⚠ Saved Cloudflare debug HTML to {debug_path}")

            if not html or "cover" not in html:
                debug_path = f"debug_{slugify_short(url, '')}.html"
                with open(debug_path, "w", encoding="utf-8") as f:
                    f.write(html or "")
                print(f"⚠ Saved debug HTML to {debug_path}")


        except Exception as e:
            print(f"⚠ Exception while fetching {url}: {e}")
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
