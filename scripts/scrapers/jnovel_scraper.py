import re
import json
import aiohttp
from bs4 import BeautifulSoup

def extract_json(text):
    try:
        return json.loads(text)
    except:
        return None

class JNovelScraper:
    def parse(self, html: str) -> str | None:
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


