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
        ld = soup.find("script", type="application/ld+json")
        if ld and ld.string:
            data = extract_json(ld.string)
            if isinstance(data, dict) and "image" in data:
                return data["image"]

        tag = soup.find("meta", property="og:image")
        if tag:
            return tag.get("content")

        return None
