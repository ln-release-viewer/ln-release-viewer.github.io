import re
import json
import aiohttp
import os
from bs4 import BeautifulSoup

def extract_json(text):
    try:
        return json.loads(text)
    except:
        return None

class JNovelScraper:
    def _debug_dump(self, html: str, url: str):
        os.makedirs("debug/jnovel", exist_ok=True)

        # Create a safe filename from the URL
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", url).strip("-")
        path = f"debug/jnovel/{slug}.html"

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(html)
            print(f"[JNOVEL DEBUG] Saved HTML to {path}")
        except Exception as e:
            print(f"[JNOVEL DEBUG] Failed to save HTML: {e}")

    async def _url_exists(self, url: str) -> bool:
        async with aiohttp.ClientSession() as session:
            async with session.head(url) as resp:
                return resp.status == 200


    async def parse(self, html: str, url: str = "", volume: int | None = None) -> str | None:
        soup = BeautifulSoup(html, "html.parser")

        if volume is not None:
            # Find the anchor for the requested volume
            anchor = soup.find("a", href=f"#volume-{volume}")
            if anchor:
                # Walk upward to a stable container
                container = anchor
                for _ in range(5):
                    container = container.parent
                    if container is None:
                        break

                # Walk backwards to find the first <img>
                img = None
                node = container.previous_sibling

                while node and not img:
                    if hasattr(node, "find"):
                        img = node.find("img")
                    node = node.previous_sibling

                if img:
                    src = img.get("src") or img.get("data-src")
                    if src:
                        # Upgrade resolution
                        url_960 = src.replace("/240/", "/960/")
                        url_480 = src.replace("/240/", "/480/")

                        for candidate in (url_960, url_480, src):
                            if await self._url_exists(candidate):
                                return candidate


        # fallback: OG image
        soup = BeautifulSoup(html, "html.parser")
        tag = soup.find("meta", property="og:image")
        if tag:
            return tag.get("content")

        return None


