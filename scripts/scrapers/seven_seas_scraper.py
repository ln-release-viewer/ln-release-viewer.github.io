import re
import os
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup


class SevenSeasScraper:
    def __init__(self, flaresolverr_url: str | None = None):
        self.flaresolverr_url = (
            flaresolverr_url
            or os.getenv("FLARESOLVERR_URL")
            or "http://localhost:8191/v1"
        )

        self.session_id = "seven_seas_session"
        self.http_session = requests.Session()

        self._init_session()

    def _init_session(self):
        """Creates a warm session in FlareSolverr and pre-solves the Cloudflare challenge."""
        try:
            # 1. Create the session
            requests.post(
                self.flaresolverr_url,
                json={"cmd": "sessions.create", "session": self.session_id},
                timeout=10,
            )
            
            # 2. Warm up session by visiting base domain to acquire cf_clearance cookie
            warmup_payload = {
                "cmd": "request.get",
                "url": "https://sevenseasentertainment.com/",
                "session": self.session_id,
                "maxTimeout": 20000
            }
            res = requests.post(self.flaresolverr_url, json=warmup_payload, timeout=25)
            data = res.json()
            
            if data.get("status") == "ok":
                # Cache clearance cookies into local requests session immediately
                solution = data.get("solution", {})
                for c in solution.get("cookies", []):
                    self.http_session.cookies.set(c["name"], c["value"], domain=c.get("domain", ""))
                
                user_agent = solution.get("userAgent")
                if user_agent:
                    self.http_session.headers.update({
                        "User-Agent": user_agent,
                        "Referer": "https://sevenseasentertainment.com/"
                    })
                print("🔥 Seven Seas FlareSolverr session successfully warmed up.")
        except Exception as e:
            print(f"⚠️ Session warmup error: {e}")

    def parse(self, html: str, base_url: str = "https://sevenseasentertainment.com") -> dict:
        soup = BeautifulSoup(html, "html.parser")
        cover_url = None
        synopsis = None

        def clean_url(url: str | None) -> str | None:
            if not url or not isinstance(url, str):
                return None
            url = url.strip()
            if url.startswith("data:"):
                return None
            if url.startswith("//"):
                return f"https:{url}"
            return url

        def is_image_url(url: str | None) -> bool:
            if not url:
                return False
            parsed = urlparse(url)
            path = parsed.path.lower()
            return any(path.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp", ".gif"])

        def extract_img_url(img_tag) -> str | None:
            if not img_tag or not hasattr(img_tag, "get"):
                return None

            # 1. Direct High-Res / Lazy Attributes
            candidates = [
                img_tag.get("data-orig-file"),
                img_tag.get("data-large-file"),
                img_tag.get("data-src"),
                img_tag.get("data-lazy-src"),
                img_tag.get("src")
            ]

            for cand in candidates:
                cleaned = clean_url(cand)
                if cleaned and is_image_url(cleaned):
                    return cleaned

            # 2. Extract from srcset attribute
            srcset = img_tag.get("srcset") or img_tag.get("data-srcset")
            if srcset and isinstance(srcset, str):
                try:
                    # Extract all image URL candidates from srcset string
                    urls = re.findall(r'(https?://[^\s,]+|/[^\s,]+)', srcset)
                    valid_urls = [clean_url(u) for u in urls if clean_url(u) and is_image_url(clean_url(u))]
                    if valid_urls:
                        # Highest resolution candidate is almost always last in srcset
                        return valid_urls[-1]
                except Exception:
                    pass

            return None

        EXCLUDED_KEYWORDS = ["logo", "header", "footer", "banner", "icon", "placeholder", "1x1", "gravatar", "button"]

        # -----------------------------------------------------------------
        # 1. Targeted Selectors (Primary Path)
        # -----------------------------------------------------------------
        selectors = [
            "#volume-cover img",
            ".series-cover img",
            ".volume-cover img",
            "div.volume-cover img",
            "#volume-cover a img",
            ".entry-content .wp-block-image img",
            "img.wp-post-image",
            ".series-description img"
        ]

        for sel in selectors:
            img = soup.select_one(sel)
            if not img:
                continue

            candidate = extract_img_url(img)
            if candidate and not any(k in candidate.lower() for k in EXCLUDED_KEYWORDS):
                cover_url = candidate
                break

        # -----------------------------------------------------------------
        # 2. OpenGraph / Meta Tag Fallbacks
        # -----------------------------------------------------------------
        if not cover_url:
            og = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "twitter:image"})
            if og and og.get("content"):
                candidate = clean_url(og["content"])
                if candidate and is_image_url(candidate) and not any(k in candidate.lower() for k in EXCLUDED_KEYWORDS):
                    cover_url = candidate

        # -----------------------------------------------------------------
        # 3. Keyword Match Fallback across all page images
        # -----------------------------------------------------------------
        if not cover_url:
            for img in soup.find_all("img"):
                src = extract_img_url(img)
                if src:
                    src_lower = src.lower()
                    if any(k in src_lower for k in ["cover", "volume", "vol_", "books"]) and not any(k in src_lower for k in EXCLUDED_KEYWORDS):
                        cover_url = src
                        break

        # -----------------------------------------------------------------
        # URL Normalization
        # -----------------------------------------------------------------
        if cover_url:
            # Resolve relative URLs against the base site URL
            cover_url = urljoin(base_url, cover_url)

        # -----------------------------------------------------------------
        # Synopsis Extraction
        # -----------------------------------------------------------------
        synopsis = None
        synopsis_paragraphs = []

        desc_container = (
            soup.select_one(".description-content")
            or soup.select_one(".series-description")
        )

        if desc_container:
            p_nodes = desc_container.select("p")
        else:
            # Fallback to .entry-content ONLY if no description container exists
            entry_content = soup.select_one(".entry-content")
            if entry_content:
                p_nodes = [
                    p for p in entry_content.select("p")
                    if not p.find_parent(id="volume-meta")
                    and not p.find_parent(class_="volume-meta")
                ]
            else:
                p_nodes = []

        # Keywords that indicate page metadata rather than story blurb content
        METADATA_KEYWORDS = [
            "▪ ▪ ▪", "RETAILERS", "Due to licensing", "Digital FAQ",
            "Series:", "Story & Art by:", "Release Date:", "Trim:", "Page Count:"
        ]

        for p in p_nodes:
            text = p.get_text(" ", strip=True)
            if not text:
                continue

            # Skip any line matching metadata indicators
            if any(k in text for k in METADATA_KEYWORDS):
                continue

            synopsis_paragraphs.append(text)

        if synopsis_paragraphs:
            synopsis = "\n\n".join(synopsis_paragraphs)

        return {
            "cover_url": cover_url,
            "synopsis": synopsis
        }

    def get_cover(self, url: str) -> dict | None:
        # Reusing a session ID allows FlareSolverr to bypass Cloudflare
        # instantly on subsequent requests using the clearance cookie
        payload = {
            "cmd": "request.get",
            "url": url,
            "session": "seven_seas_session",
            "maxTimeout": 15000  # Lower timeout ceiling from 60s to 15s
        }
        try:
            res = requests.post(self.flaresolverr_url, json=payload, timeout=20)
            data = res.json()
            if data.get("status") == "ok":
                html = data["solution"]["response"]
                return self.parse(html, base_url=url)
            else:
                print(f"⚠️ FlareSolverr status failed for {url}: {data.get('message')}")
                return None
        except Exception as e:
            print(f"❌ Error connecting to FlareSolverr for {url}: {e}")
            return None

    def close(self):
        pass

flaresolverr_endpoint = os.getenv("FLARESOLVERR_URL", "http://localhost:8191/v1")
scraper = SevenSeasScraper(flaresolverr_url=flaresolverr_endpoint)
