import re
import json
from bs4 import BeautifulSoup

def extract_json(text):
    try:
        return json.loads(text)
    except:
        return None

YEN_PLACEHOLDER_PATTERNS = [
    "placeholder",
    "default",
    "noimage",
    "comingsoon",
    "logo",
    "icon",
]

class YenPressScraper:
    def parse(self, html: str) -> str | None:
        soup = BeautifulSoup(html, "html.parser")

        # -----------------------------------------
        # 1. __NEXT_DATA__ (primary, most reliable)
        # -----------------------------------------
        script = soup.find("script", id="__NEXT_DATA__")
        if script and script.string:
            data = extract_json(script.string)
            if data:
                try:
                    # Try multiple known structures
                    pp = data["props"]["pageProps"]

                    # A) dehydratedState → queries → state → data → cover
                    queries = (
                        pp.get("dehydratedState", {})
                        .get("queries", [])
                    )
                    for q in queries:
                        d = q.get("state", {}).get("data", {})
                        cover = d.get("cover")
                        if cover and not self._is_bad(cover):
                            return cover

                    # B) product.cover
                    product = pp.get("product", {})
                    cover = product.get("cover")
                    if cover and not self._is_bad(cover):
                        return cover

                    # C) product.images.cover
                    images = product.get("images", {})
                    cover = images.get("cover")
                    if cover and not self._is_bad(cover):
                        return cover

                except Exception:
                    pass

        # -----------------------------------------
        # 2. JSON-LD fallback
        # -----------------------------------------
        for tag in soup.find_all("script", type="application/ld+json"):
            data = extract_json(tag.string or "")
            if isinstance(data, dict):
                img = data.get("image")
                if isinstance(img, str) and not self._is_bad(img):
                    return img
                if isinstance(img, list) and img:
                    if not self._is_bad(img[0]):
                        return img[0]
        
        # 3. Yen Press real cover: <div class="series-cover">
        series_cover = soup.find("div", class_="series-cover")
        if series_cover:
            img = series_cover.find("img")
            if img:
                src = img.get("src") or img.get("data-src") or img.get("srcset")
                if src and not self._is_bad(src):
                    return src

        # 4. <img class="img-box-shadow ...">
        for img in soup.find_all("img", class_=lambda c: c and "img-box-shadow" in c):
            src = img.get("src") or img.get("data-src") or img.get("srcset")
            if src and not self._is_bad(src):
                return src

        # -----------------------------------------
        # 4. <figure> blocks (common for LN covers)
        # -----------------------------------------
        for fig in soup.find_all("figure"):
            img = fig.find("img")
            if img:
                src = img.get("src") or img.get("data-src")
                if src and not self._is_bad(src):
                    return src

        # -----------------------------------------
        # 5. <img> tags (lazy-loaded, data-src, etc.)
        # -----------------------------------------
        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src") or ""
            if src and not self._is_bad(src):
                return src

        return None

    def _is_bad(self, url: str) -> bool:
        """Reject placeholders, icons, logos, and tiny images."""
        u = url.lower()

        # Reject placeholders
        if any(p in u for p in YEN_PLACEHOLDER_PATTERNS):
            return True

        # Reject icons
        if "icon" in u or "favicon" in u:
            return True

        # Reject tiny thumbnails
        if "150x150" in u or "300x300" in u:
            return True

        return False

    def _debug_dump(self, html: str, url: str):
        # Create a safe slug from the URL
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", url).strip("-")
        path = f"debug/yenpress_{slug}.html"

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(html)
            print(f"[YEN DEBUG] Saved HTML to {path}")
        except Exception as e:
            print(f"[YEN DEBUG] Failed to save HTML: {e}")
