import re
import json
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
                    # TODO: pick latest volume instead of first
                    for v in volumes:
                        if "cover" in v:
                            return v["cover"]
                except:
                    pass

        # fallback: OG
        soup = BeautifulSoup(html, "html.parser")
        tag = soup.find("meta", property="og:image")
        if tag:
            return tag.get("content")

        return None
