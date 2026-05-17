import json
import re
from bs4 import BeautifulSoup

def extract_json(text):
    try:
        return json.loads(text)
    except Exception:
        return None

def title_similarity(a: str, b: str) -> float:
    a_tokens = set(re.findall(r"\w+", a.lower()))
    b_tokens = set(re.findall(r"\w+", b.lower()))

    if not a_tokens or not b_tokens:
        return 0.0

    overlap = len(a_tokens & b_tokens)
    return overlap / len(a_tokens)

class GenericScraper:
    """
    Fallback scraper for publishers without a dedicated parser.
    Attempts:
      1. <meta property="og:image">
      2. <script type="application/ld+json"> with "image"
      3. <img> tags that look like covers
    """

    def parse(self, html: str, expected_title: str | None = None) -> str | None:
        soup = BeautifulSoup(html, "html.parser")

        actual_og_title = soup.find("meta", property="og:title")
        if expected_title:
            score = title_similarity(expected_title, actual_og_title)
            if score < 0.5:
                return None

        # 1. OG title mismatch → homepage redirect → invalid product
 #       og_title = soup.find("meta", property="og:title")
 #       if expected_title and og_title:
 #           actual = og_title.get("content", "").strip().lower()
 #           expected = expected_title.strip().lower()

            # If the OG title does not contain the expected title, reject
 #           if expected not in actual:
 #               return None


        # Detect Shopify 404s
        # 1. OG title says 404
        og_title = soup.find("meta", property="og:title")
        if og_title:
            title = og_title.get("content", "").lower()
            if "404" in title or "not found" in title:
                return None

        # 2. Shopify 404 text
        if soup.find(string=lambda s: s and "page does not exist" in s.lower()):
            return None

        # 3. TOKYOPOP-specific 404 signature
        if soup.find("h1", string=lambda s: s and "404" in s):
            return None


        # 1. OG image
        og = soup.find("meta", property="og:image")
        if og and og.get("content"):
            return og["content"]

        # 2. JSON-LD with "image"
        for tag in soup.find_all("script", type="application/ld+json"):
            if not tag.string:
                continue
            data = extract_json(tag.string)
            if isinstance(data, dict):
                img = data.get("image")
                if isinstance(img, str):
                    return img
                if isinstance(img, list) and img:
                    return img[0]

        # 3. Look for <img> tags that look like covers
        #    (common pattern: filenames with "cover", "volume", "vol", etc.)
        for img in soup.find_all("img"):
            src = img.get("src") or ""
            if any(k in src.lower() for k in ["cover", "volume", "vol", "jacket"]):
                return src

        return None
