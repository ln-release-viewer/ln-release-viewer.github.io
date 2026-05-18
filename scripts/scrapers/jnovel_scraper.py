import re
import json
import aiohttp
import os
from bs4 import BeautifulSoup
from urllib.parse import urljoin

def extract_json(text):
    try:
        return json.loads(text)
    except:
        return None

def normalize_fractional_volume(vol: str) -> str:
    """Convert 8.1 → '8 part 1', 12.2 → '12 act 2'."""
    if "." not in vol:
        return f"volume {vol}"

    base, frac = vol.split(".")
    frac = frac.strip()

    # J-Novel uses "Part" or "Act" depending on series, but matching either works
    return f"{base} {frac}"

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
            # Find the volume container directly
            container = soup.find("div", id=f"volume-{volume}")
            if container:
                # Find the first image inside this volume block
                img = container.find("img")
                if img:
                    src = img.get("src") or img.get("data-src")
                    if src:
                        # Upgrade resolution
                        url_960 = src.replace("/240/", "/960/")
                        url_480 = src.replace("/240/", "/480/")

                        for candidate in (url_960, url_480, src):
                            if await self._url_exists(candidate):
                                return candidate

                        return src

        # If we have a fractional volume, we must fuzzy-match
        if volume:
            expected = normalize_fractional_volume(str(volume)).lower()

            anchors = soup.find_all("a", href=re.compile(r"#volume-(\d+)"))
            candidates = []

            for a in anchors:
                text = a.get_text(strip=True).lower()

                # Basic fuzzy match: check if expected tokens appear in the title
                score = sum(1 for tok in expected.split() if tok in text)

                if score > 0:
                    # Find the image BEFORE the anchor
                    block = a.find_parent()
                    if block:
                        img = block.find("img")
                        if img:
                            src = img.get("src") or img.get("data-src")
                            if src:
                                candidates.append((score, src))

            if candidates:
                # Pick the best-scoring match
                candidates.sort(key=lambda x: x[0], reverse=True)
                src = candidates[0][1]

                # Upgrade resolution
                url_960 = src.replace("/240/", "/960/")
                url_480 = src.replace("/240/", "/480/")

                for candidate in (url_960, url_480, src):
                    return candidate

        # fallback: OG image
        soup = BeautifulSoup(html, "html.parser")
        tag = soup.find("meta", property="og:image")
        if tag:
            return tag.get("content")

        return None


