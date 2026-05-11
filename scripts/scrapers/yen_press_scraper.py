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
        soup = BeautifulSoup(html, "html.parser")

        # -----------------------------------------
        # 1. __NEXT_DATA__ (primary)
        # -----------------------------------------
        match = re.search(
            r'<script id="__NEXT_DATA__"[^>]*>(.+?)</script>',
            html,
            re.DOTALL,
        )
        if match:
            data = extract_json(match.group(1))
            if data:
                # Newer Yen Press pages sometimes nest differently
                try:
                    queries = (
                        data["props"]["pageProps"]
                        .get("dehydratedState", {})
                        .get("queries", [])
                    )
                    for q in queries:
                        d = q.get("state", {}).get("data", {})
                        cover = d.get("cover")
                        if cover:
                            return cover
                except:
                    pass

        # -----------------------------------------
        # 2. JSON-LD fallback
        # -----------------------------------------
        for tag in soup.find_all("script", type="application/ld+json"):
            data = extract_json(tag.string or "")
            if isinstance(data, dict):
                img = data.get("image")
                if isinstance(img, str):
                    return img
                if isinstance(img, list) and img:
                    return img[0]

        # -----------------------------------------
        # 3. OG image fallback
        # -----------------------------------------
        og = soup.find("meta", property="og:image")
        if og and og.get("content"):
            return og["content"]

        # -----------------------------------------
        # 4. <img> tag heuristic fallback
        # -----------------------------------------
        for img in soup.find_all("img"):
            src = img.get("src") or ""
            if any(k in src.lower() for k in ["cover", "jacket", "volume", "vol"]):
                return src

        return None
