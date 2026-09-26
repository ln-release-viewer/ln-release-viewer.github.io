import re
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup


class HanashiMediaScraper:
    def __init__(self, **kwargs):
        pass

    def parse(self, html: str, base_url: str = "https://hanashi.media") -> dict:
        soup = BeautifulSoup(html, "html.parser")
        cover_url = None
        synopsis = None

        # -----------------------------------------------------------------
        # 1. Cover Image Extraction
        # -----------------------------------------------------------------
        # Target SvelteKit container or Hanashi store-api cover image endpoint
        img_candidates = [
            # High precision: image inside aspect ratio container
            soup.select_one("div.aspect-\\[2\\/3\\] img"),
            # Attribute match: store API endpoint URL
            soup.select_one('img[src*="store-api.hanashi.media/ebooks/cover"]'),
            # Fallback container buttons
            soup.select_one('button[aria-label="View full size"] img'),
            # OpenGraph fallback
            soup.find("meta", property="og:image"),
        ]

        for cand in img_candidates:
            if not cand:
                continue

            # Handle meta vs img tag attributes
            src = cand.get("content") if cand.name == "meta" else (
                cand.get("src") or cand.get("data-src")
            )

            if src and isinstance(src, str) and not src.startswith("data:"):
                cover_url = src.strip()
                break

        if cover_url:
            cover_url = urljoin(base_url, cover_url)

        # -----------------------------------------------------------------
        # 2. Synopsis Extraction
        # -----------------------------------------------------------------
        # High precision: Svelte text block with whitespace-pre-wrap class
        synopsis_div = soup.select_one("div.whitespace-pre-wrap")

        # Fallback: Look for section containing "Story" heading
        if not synopsis_div:
            for h3 in soup.find_all("h3"):
                if "story" in h3.get_text().strip().lower():
                    parent_section = h3.find_parent("section")
                    if parent_section:
                        synopsis_div = parent_section.select_one("div")
                        break

        if synopsis_div:
            text = synopsis_div.get_text("\n", strip=True)
            if text:
                synopsis = text

        return {
            "cover_url": cover_url,
            "synopsis": synopsis
        }