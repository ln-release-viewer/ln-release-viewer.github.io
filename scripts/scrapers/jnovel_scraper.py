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


    async def parse(self, html: str, url: str = "") -> str | None:
        # -----------------------------------------
        # 2. HTML fallback: parse volume blocks
        # -----------------------------------------
        soup = BeautifulSoup(html, "html.parser")

        # Find all volume anchors
        anchors = soup.find_all("a", href=re.compile(r"#volume-(\d+)"))

        volumes = []
        for a in anchors:
            m = re.search(r"#volume-(\d+)", a["href"])
            if not m:
                continue

            vol_num = int(m.group(1))

            # The cover is usually in the next sibling block
            block = a.find_parent()
            if not block:
                continue

            img = block.find("img")
            if not img:
                continue

            src = img.get("src") or img.get("data-src")
            if not src:
                continue

            volumes.append((vol_num, src))

        # Sort by volume number descending
        volumes.sort(key=lambda x: x[0], reverse=True)

        # Return the highest volume cover
        if volumes:
            vol_num, url = volumes[0]

            # Upgrade resolution
            url_960 = url.replace("/240/", "/960/")
            url_480 = url.replace("/240/", "/480/")

            for candidate in (url_960, url_480, url):
                if await self._url_exists(candidate):
                    return candidate


        # fallback: OG image
        soup = BeautifulSoup(html, "html.parser")
        tag = soup.find("meta", property="og:image")
        if tag:
            return tag.get("content")

        return None


