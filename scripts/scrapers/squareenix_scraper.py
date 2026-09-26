import html
import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup


class SquareEnixScraper:
    async def parse(self, html_content: str, url: str) -> dict | None:
        soup = BeautifulSoup(html_content, "html.parser")

        cover_url = None
        synopsis = None

        # Excluded keywords for banners, UI icons, and footers
        EXCLUDED_KEYWORDS = ["banner", "logo", "icon", "footer", "header", "hero", "promo", "background"]

        def score_img(img) -> int:
            """Scores image tags based on likelihood of being the book cover."""
            score = 0
            
            # 1. Attribute checks
            alt = (img.get("alt") or "").lower()
            src = (img.get("src") or "").lower()
            srcset = (img.get("srcset") or img.get("imageSrcSet") or "").lower()

            # Disqualify obvious non-covers
            if any(k in alt or k in src or k in srcset for k in EXCLUDED_KEYWORDS):
                return -100

            # 2. Check parent container classes
            parent = img.find_parent(class_=True)
            parent_classes = " ".join(parent.get("class", [])).lower() if parent else ""

            if "aspect-" in parent_classes or "cover" in parent_classes:
                score += 50

            # 3. Specific Square Enix CDN or Next.js indicators
            if "fyre.cdn.sewest.net" in src or "fyre.cdn.sewest.net" in srcset:
                score += 30

            # 4. Filename keywords
            if any(k in src or k in srcset or k in alt for k in ["cover", "vol", "volume", "_ln_"]):
                score += 40

            # 5. Presence of Next.js image attributes
            if img.get("data-nimg"):
                score += 10

            return score

        # -----------------------------------------------------------------
        # 1. Target <link rel="preload"> or <img> elements
        # -----------------------------------------------------------------
        candidates = []

        # Check preload link tags (often contains full-res cover preload)
        for link in soup.find_all("link", rel="preload", attrs={"as": "image"}):
            srcset = link.get("imagesrcset") or link.get("imageSrcSet") or link.get("href")
            if srcset and "fyre.cdn.sewest.net" in srcset and not any(k in srcset.lower() for k in EXCLUDED_KEYWORDS):
                candidates.append((link, 60))  # High priority baseline score for preloaded cover assets

        # Check standard img tags
        for img in soup.find_all("img"):
            score = score_img(img)
            if score > 0:
                candidates.append((img, score))

        # Sort candidates by highest score
        candidates.sort(key=lambda x: x[1], reverse=True)

        if candidates:
            best_tag = candidates[0][0]

            # Extract highest-res URL from srcset / imageSrcSet or fallback to src/href
            srcset = (
                best_tag.get("imagesrcset")
                or best_tag.get("imageSrcSet")
                or best_tag.get("srcset")
            )

            if srcset:
                urls = re.findall(r'(https?://[^\s,]+)', srcset)
                if urls:
                    cover_url = urls[-1]  # Highest width variant is last in srcset

            if not cover_url:
                cover_url = best_tag.get("src") or best_tag.get("href")

        # OpenGraph fallback
        if not cover_url:
            og_img = soup.find("meta", property="og:image")
            if og_img and og_img.get("content"):
                cover_url = og_img["content"]

        # Maximize resolution: Ensure width=768 or higher on Square Enix CDN URL
        if cover_url and "fyre.cdn.sewest.net" in cover_url:
            cover_url = re.sub(r'width=\d+', 'width=768', cover_url)

        # 2. Synopsis Extraction (from escaped meta description tag)
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            raw_meta = meta_desc["content"]
            # Unescape HTML entities (&lt;p&gt; -> <p>)
            unescaped_meta = html.unescape(raw_meta)
            
            # Parse inner HTML tags inside the meta content
            desc_soup = BeautifulSoup(unescaped_meta, "html.parser")
            p_texts = [p.get_text(strip=True) for p in desc_soup.find_all("p") if p.get_text(strip=True)]
            
            if p_texts:
                synopsis = "\n\n".join(p_texts)
            else:
                # Fallback to direct raw text if no <p> tags were encoded
                clean_text = desc_soup.get_text(strip=True)
                if clean_text:
                    synopsis = clean_text

        return {
            "cover_url": cover_url,
            "synopsis": synopsis
        }