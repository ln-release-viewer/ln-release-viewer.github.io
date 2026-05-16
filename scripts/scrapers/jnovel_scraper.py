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

    def parse(self, html: str, url: str = "") -> str | None:
        self._debug_dump(html, url)
        match = re.search(r"window\.__NUXT__\s*=\s*(\{.*?\});", html, re.DOTALL)
        if match:
            data = extract_json(match.group(1))
            if data:
                try:
                    volumes = data["state"]["data"].get("volumes", [])
                    if volumes:
                        # Sort by volume number descending
                        volumes_sorted = sorted(
                            volumes,
                            key=lambda v: v.get("number", 0),
                            reverse=True
                        )

                        for v in volumes_sorted:
                            cover = v.get("cover")
                            if not cover:
                                continue

                            # Prefer explicit fields
                            url = (
                                cover.get("originalUrl")
                                or cover.get("coverUrl")
                                or (cover if isinstance(cover, str) else None)
                            )

                            if not url:
                                continue

                            return url

                except Exception:
                    pass

        # fallback: OG image
        soup = BeautifulSoup(html, "html.parser")
        tag = soup.find("meta", property="og:image")
        if tag:
            return tag.get("content")

        return None


