import json
import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup


def extract_json(text):
    try:
        return json.loads(text)
    except Exception:
        return None


YEN_PLACEHOLDER_PATTERNS = [
    "placeholder",
    "default",
    "noimage",
    "comingsoon",
    "logo",
    "icon",
    "og-image",
    "banner",
]


class YenPressScraper:
    def parse(self, html: str, url: str = "https://yenpress.com") -> dict:
        """Parses Yen Press volume HTML and returns normalized cover & synopsis."""
        soup = BeautifulSoup(html, "html.parser")

        raw_cover = self._extract_cover(soup)
        full_cover = urljoin(url, raw_cover) if raw_cover else None

        return {
            "cover_url": full_cover,
            "synopsis": self._extract_synopsis(soup),
        }

    # -------------------------------------------------------------------------
    # Synopsis Extraction
    # -------------------------------------------------------------------------
    def _extract_synopsis(self, soup: BeautifulSoup) -> str | None:
        """Extracts synopsis from JSON-LD or .content-heading-txt (choosing the longest text)."""
        
        # 1. Primary: Try JSON-LD first as it contains untruncated structured metadata
        for tag in soup.find_all("script", type="application/ld+json"):
            data = extract_json(tag.string or "")
            if isinstance(data, dict):
                desc = data.get("description")
                if desc and isinstance(desc, str) and len(desc.strip()) > 50:
                    return desc.strip()

        # 2. Secondary: DOM Extraction (Collect all candidates and take the longest)
        candidates = []
        
        # Target containers with content-heading-txt class
        for container in soup.find_all("div", class_=lambda c: c and "content-heading-txt" in c):
            # Gather text from paragraphs or the container itself
            paragraphs = container.find_all(["p", "div"], class_=lambda c: c and "paragraph" in c) or container.find_all("p")
            if paragraphs:
                for p in paragraphs:
                    text = p.get_text(separator=" ", strip=True)
                    if text:
                        candidates.append(text)
            else:
                text = container.get_text(separator=" ", strip=True)
                if text:
                    candidates.append(text)

        if candidates:
            # Return the candidate with the longest text length to avoid truncated previews
            return max(candidates, key=len)

        # 3. Fallback: Meta description tag
        meta_desc = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
        if meta_desc and meta_desc.get("content"):
            return meta_desc["content"].strip()

        return None

    # -------------------------------------------------------------------------
    # Cover Image Extraction
    # -------------------------------------------------------------------------
    def _extract_cover(self, soup: BeautifulSoup) -> str | None:
        # 1. __NEXT_DATA__ (primary, most reliable for Next.js apps)
        script = soup.find("script", id="__NEXT_DATA__")
        if script and script.string:
            data = extract_json(script.string)
            if data:
                try:
                    pp = data["props"]["pageProps"]

                    # A) dehydratedState -> queries -> state -> data -> cover
                    queries = pp.get("dehydratedState", {}).get("queries", [])
                    for q in queries:
                        d = q.get("state", {}).get("data", {})
                        cover = d.get("cover")
                        if cover and not self._is_bad(cover):
                            return cover

                    # B) product.cover / images.cover
                    product = pp.get("product", {})
                    cover = product.get("cover") or product.get("images", {}).get("cover")
                    if cover and not self._is_bad(cover):
                        return cover
                except Exception:
                    pass

        # 2. Targeted DOM Selector: <div class="book-cover-img"> or <div class="series-cover">
        cover_container = soup.find("div", class_=lambda c: c and ("book-cover-img" in c or "series-cover" in c))
        if cover_container:
            img = cover_container.find("img")
            if img:
                # b-lazy images can store the target in data-src or src
                src = img.get("data-src") or img.get("src") or img.get("srcset")
                if src and not self._is_bad(src):
                    return src

        # 3. Class-based fallback: <img class="img-box-shadow...">
        for img in soup.find_all("img", class_=lambda c: c and "img-box-shadow" in c):
            src = img.get("data-src") or img.get("src") or img.get("srcset")
            if src and not self._is_bad(src):
                return src

        # 4. JSON-LD fallback
        for tag in soup.find_all("script", type="application/ld+json"):
            data = extract_json(tag.string or "")
            if isinstance(data, dict):
                img = data.get("image")
                if isinstance(img, str) and not self._is_bad(img):
                    return img
                if isinstance(img, list) and img and not self._is_bad(img[0]):
                    return img[0]

        # Explicitly return None if no actual book cover container was matched!
        # Do NOT iterate through all loose <img> tags on the page.
        return None

    def _is_bad(self, url: str) -> bool:
        """Reject placeholders, icons, logos, site banners, and tiny images."""
        u = url.lower()
        if any(p in u for p in YEN_PLACEHOLDER_PATTERNS):
            return True
        if "icon" in u or "favicon" in u:
            return True
        if "150x150" in u or "300x300" in u:
            return True
        return False
