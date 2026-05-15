import json
import re
from bs4 import BeautifulSoup

def extract_json(text):
    try:
        return json.loads(text)
    except:
        return None

class BookWalkerScraper:
    def parse(self, html: str) -> str | None:
        soup = BeautifulSoup(html, "html.parser")

        # 1. Extract Next.js data (most reliable)
        script = soup.find("script", id="__NEXT_DATA__")
        if script and script.string:
            data = extract_json(script.string)
            if data:
                try:
                    product = data["props"]["pageProps"]["product"]

                    # Prefer full-size image
                    url = product.get("imageUrl") or product.get("thumbnailUrl")
                    if url:
                        # Reject BookWalker placeholders
                        if "noimage" in url.lower() or "comingsoon" in url.lower():
                            return None
                        return url
                except Exception:
                    pass

        # 2. Fallback: JSON-LD (rarely used by BookWalker)
        for tag in soup.find_all("script", type="application/ld+json"):
            data = extract_json(tag.string or "")
            if not isinstance(data, dict):
                continue

            # Direct image
            img = data.get("image")
            if isinstance(img, str):
                return img
            if isinstance(img, list) and img:
                return img[0]

            # Thumbnail
            thumb = data.get("thumbnailUrl")
            if isinstance(thumb, str):
                return thumb
            if isinstance(thumb, list) and thumb:
                return thumb[0]

        # 3. OG image fallback (last resort)
        tag = soup.find("meta", property="og:image")
        if tag:
            url = tag.get("content")
            if url and not url.endswith(".ico"):
                return url

        return None

