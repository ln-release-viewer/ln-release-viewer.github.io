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

        vol_str = str(volume)
        if volume is not None and "." not in vol_str:
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

        # If we have a fractional volume, we must go through all volumes
        if "." in vol_str:
            base, frac = vol_str.split(".", 1)
            base = base.strip()
            frac = frac.strip()

            anchors = soup.find_all("a", href=re.compile(r"#volume-(\d+)"))
            candidates = []

            for a in anchors:
                text = a.get_text(strip=True).lower()

                # Require the base volume number
                if f"volume {base}" not in text:
                    continue

                # Require some kind of split indicator
                if "part" not in text and "act" not in text:
                    continue

                # Distinguish .1 vs .2
                if frac == "1" and not any(w in text for w in ["one", "1", "i"]):
                    continue
                if frac == "2" and not any(w in text for w in ["two", "2", "ii"]):
                    continue

                block = a.find_parent()
                if block:
                    img = block.find("img")
                    if img:
                        src = img.get("src") or img.get("data-src")
                        if src:
                            candidates.append(src)

            if candidates:
                src = candidates[0]

                url_960 = src.replace("/240/", "/960/")
                url_480 = src.replace("/240/", "/480/")

                for candidate in (url_960, url_480, src):
                    return candidate

        # fallback: OG image
        tag = soup.find("meta", property="og:image")
        if tag:
            return tag.get("content")


        return None


