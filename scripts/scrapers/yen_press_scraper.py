import re
import json
from bs4 import BeautifulSoup

def extract_json(text):
    try:
        return json.loads(text)
    except:
        return None

class YenPressScraper:
    def parse(self, html: str) -> str | None:
        # __NEXT_DATA__
        match = re.search(
            r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>',
            html,
            re.DOTALL,
        )
        if match:
            data = extract_json(match.group(1))
            if data:
                try:
                    queries = data["props"]["pageProps"]["dehydratedState"]["queries"]
                    for q in queries:
                        d = q.get("state", {}).get("data", {})
                        if "cover" in d:
                            return d["cover"]
                except:
                    pass

        # fallback: OG image
        soup = BeautifulSoup(html, "html.parser")
        tag = soup.find("meta", property="og:image")
        if tag:
            return tag.get("content")

        return None
