import html
import json
import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup


def extract_json(text: str):
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
    def parse(self, html_content: str, expected_title: str | None = None, base_url: str = "") -> dict:
        soup = BeautifulSoup(html_content, "html.parser")

        # -----------------------------------------------------------------
        # 1. Direct 404 / Missing Product Page Detection
        # -----------------------------------------------------------------
        actual_og_title = soup.find("meta", property="og:title")
        page_title = soup.find("title")

        title_text = ""
        if actual_og_title and actual_og_title.get("content"):
            title_text = actual_og_title["content"].lower()
        elif page_title and page_title.string:
            title_text = page_title.string.lower()

        # Check title tags for common error signatures
        if any(err in title_text for err in ["404", "not found", "page missing"]):
            return {"cover_url": "404_NOT_FOUND", "synopsis": None}

        # Check DOM text for Shopify / generic platform 404 banners
        if soup.find(string=lambda s: s and any(k in s.lower() for k in ["page does not exist", "page not found", "product not found"])):
            return {"cover_url": "404_NOT_FOUND", "synopsis": None}

        if soup.find("h1", string=lambda s: s and ("404" in s or "not found" in s.lower())):
            return {"cover_url": "404_NOT_FOUND", "synopsis": None}

        # Check title similarity if an expected title was passed
        if expected_title and title_text:
            score = title_similarity(expected_title, title_text)
            if score < 0.35:
                # Page loaded, but content is for an entirely different product or redirection landing
                return {"cover_url": "404_NOT_FOUND", "synopsis": None}

        cover_url = None
        synopsis = None

        # -----------------------------------------------------------------
        # 2. JSON-LD Schema (Tokyopop / Shopify)
        # -----------------------------------------------------------------
        for tag in soup.find_all("script", type="application/ld+json"):
            if not tag.string:
                continue

            data = extract_json(tag.string)
            if not data:
                continue

            items = data if isinstance(data, list) else [data]

            for item in items:
                if not isinstance(item, dict):
                    continue

                if not cover_url:
                    img = item.get("image")
                    if isinstance(img, str):
                        cover_url = img
                    elif isinstance(img, list) and img:
                        cover_url = img[0] if isinstance(img[0], str) else img[0].get("url")
                    elif isinstance(img, dict):
                        cover_url = img.get("url")

                if not synopsis:
                    desc = item.get("description")
                    if desc and isinstance(desc, str):
                        clean_desc = BeautifulSoup(desc, "html.parser").get_text("\n\n", strip=True)
                        if clean_desc and len(clean_desc) > 30:
                            synopsis = clean_desc

        # -----------------------------------------------------------------
        # 3. Fallback Cover Extraction
        # -----------------------------------------------------------------
        if not cover_url:
            og_img = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "twitter:image"})
            if og_img and og_img.get("content"):
                cover_url = og_img["content"]

        if not cover_url:
            for img in soup.find_all("img"):
                src = img.get("src") or img.get("data-src") or ""
                if any(k in src.lower() for k in ["cover", "volume", "vol", "jacket", "product"]):
                    cover_url = src
                    break

        if cover_url:
            cover_url = cover_url.strip()
            # Strip Shopify dimension tags (e.g. _100x100.jpg, _300x.jpg)
            cover_url = re.sub(r'_(?:small|medium|large|grande|\d+x\d*|\d*x\d+)(\.(?:jpg|jpeg|png|webp))', r'\1', cover_url, flags=re.IGNORECASE)
            cover_url = cover_url.split("?")[0]
            if base_url and not cover_url.startswith("http"):
                cover_url = urljoin(base_url, cover_url)

        # -----------------------------------------------------------------
        # 4. Fallback Synopsis Extraction
        # -----------------------------------------------------------------
        if not synopsis:
            meta_sources = [
                soup.find("meta", property="og:description"),
                soup.find("meta", attrs={"name": "description"}),
                soup.find("meta", attrs={"name": "twitter:description"}),
            ]

            for meta in meta_sources:
                if meta and meta.get("content"):
                    clean_content = html.unescape(meta["content"].strip())
                    clean_text = BeautifulSoup(clean_content, "html.parser").get_text(strip=True)

                    if clean_text and len(clean_text) > 20:
                        synopsis = clean_text
                        break

        return {
            "cover_url": cover_url,
            "synopsis": synopsis
        }