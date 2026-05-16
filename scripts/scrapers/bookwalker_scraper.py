import json
import re
from bs4 import BeautifulSoup

def extract_json(text):
    try:
        return json.loads(text)
    except:
        return None

BOOKWALKER_ICON_PATTERNS = [
    "favicon", "apple-icon", "icon.png", "ogp", "default", "logo"
]

BOOKWALKER_PLACEHOLDER_PATTERNS = [
    "noimage", "comingsoon", "no-cover", "nocover", "placeholder"
]

class BookWalkerScraper:
    def parse(self, html: str) -> str | None:
        soup = BeautifulSoup(html, "html.parser")

        # 1. Extract Next.js data (always correct)
        script = soup.find("script", id="__NEXT_DATA__")
        if script and script.string:
            data = extract_json(script.string)
            if data:
                try:
                    product = data["props"]["pageProps"]["product"]
                    url = product.get("imageUrl") or product.get("thumbnailUrl")
                    if url:
                        u = url.lower()

                        # Reject icons
                        if any(p in u for p in BOOKWALKER_ICON_PATTERNS):
                            return None

                        # Reject placeholders
                        if any(p in u for p in BOOKWALKER_PLACEHOLDER_PATTERNS):
                            return None

                        return url
                except Exception:
                    pass

        # 2. JSON-LD fallback (rare)
        for tag in soup.find_all("script", type="application/ld+json"):
            data = extract_json(tag.string or "")
            if not isinstance(data, dict):
                continue

            img = data.get("image")
            if isinstance(img, str):
                if not any(p in img.lower() for p in BOOKWALKER_ICON_PATTERNS):
                    return img

            if isinstance(img, list) and img:
                return img[0]

        # 3. OG image fallback (last resort)
        tag = soup.find("meta", property="og:image")
        if tag:
            url = tag.get("content")
            if url and not any(p in url.lower() for p in BOOKWALKER_ICON_PATTERNS):
                return url

        return None


