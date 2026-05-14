import json
from bs4 import BeautifulSoup

def extract_json(text):
    try:
        return json.loads(text)
    except:
        return None

class BookWalkerScraper:
    def parse(self, html: str) -> str | None:
        soup = BeautifulSoup(html, "html.parser")

        # 1. JSON-LD
        for tag in soup.find_all("script", type="application/ld+json"):
            data = extract_json(tag.string or "")
            if not isinstance(data, dict):
                continue

            # Direct image
            if isinstance(data.get("image"), str):
                return data["image"]

            # Image list
            if isinstance(data.get("image"), list) and data["image"]:
                return data["image"][0]

            # Thumbnail
            if isinstance(data.get("thumbnailUrl"), str):
                return data["thumbnailUrl"]

            if isinstance(data.get("thumbnailUrl"), list) and data["thumbnailUrl"]:
                return data["thumbnailUrl"][0]

            # Offers
            offers = data.get("offers", {})
            if isinstance(offers, dict) and "image" in offers:
                return offers["image"]

            # Work examples
            work = data.get("workExample")
            if isinstance(work, list):
                for w in work:
                    if isinstance(w, dict) and "image" in w:
                        return w["image"]

        # 2. OG image fallback
        tag = soup.find("meta", property="og:image")
        if tag:
            return tag.get("content")

        return None
