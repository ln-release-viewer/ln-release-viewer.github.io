import re
import json
import aiohttp
from bs4 import BeautifulSoup

def extract_json(text):
    try:
        return json.loads(text)
    except:
        return None

async def try_url(url: str) -> str | None:
    """Return URL if it exists (HTTP 200), else None."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.head(url, timeout=5) as resp:
                if resp.status == 200:
                    return url
    except:
        pass
    return None


class JNovelScraper:
    async def parse(self, html: str) -> str | None:
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

                            # If URL contains a size folder, try upgrading
                            m = re.search(r"/img/(\d+)/webp/(.+)$", url)
                            if m:
                                _, tail = m.groups()
                                for size in ["960", "480", "240"]:
                                    test_url = f"https://cdn.j-novel.club/pub/img/{size}/webp/{tail}"
                                    working = await try_url(test_url)
                                    if working:
                                        return working

                            # Otherwise return the original
                            return url

                except Exception:
                    pass

        # fallback: OG image
        soup = BeautifulSoup(html, "html.parser")
        tag = soup.find("meta", property="og:image")
        if tag:
            return tag.get("content")

        return None


