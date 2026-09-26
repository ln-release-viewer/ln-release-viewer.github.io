import os
import re
import requests
from urllib.parse import quote_plus
from difflib import SequenceMatcher
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
}

STOPWORDS = {"a", "an", "the", "in", "on", "of", "to", "for", "with", "and", "or", "is", "at", "by"}
NUM_WORDS = {
    "1": ["1", "one", "i"],
    "2": ["2", "two", "ii"],
    "3": ["3", "three", "iii"],
    "4": ["4", "four", "iv"],
    "5": ["5", "five", "v"],
    "6": ["6", "six", "vi"],
    "7": ["7", "seven", "vii"],
    "8": ["8", "eight", "viii"],
    "9": ["9", "nine", "ix"],
    "10": ["10", "ten", "x"],
}


class BookWalkerProvider:
    def __init__(self, flaresolverr_url: str | None = None, session_id: str = "bw_scraper_session"):
        # Dynamically pull from FLARESOLVERR_URL env var, or fallback to localhost
        self.flaresolverr_url = flaresolverr_url or os.getenv("FLARESOLVERR_URL", "http://localhost:8191/v1")
        self.session_id = session_id
        self._init_session()

    def _init_session(self):
        """Creates a persistent session in FlareSolverr to store Cloudflare cookies."""
        payload = {
            "cmd": "sessions.create",
            "session": self.session_id
        }
        try:
            res = requests.post(self.flaresolverr_url, json=payload, timeout=10)
            if res.status_code == 200:
                print(f"[BW] Created/reused FlareSolverr session: {self.session_id}")
        except Exception as e:
            print(f"[BW] Warning: Could not create FlareSolverr session on {self.flaresolverr_url}: {e}")

    def fetch_page_flaresolverr(self, url: str) -> str | None:
        """Executes GET request using the persistent FlareSolverr session."""
        payload = {
            "cmd": "request.get",
            "url": url,
            "session": self.session_id,
            "maxTimeout": 30000,
            "headers": HEADERS
        }
        try:
            res = requests.post(self.flaresolverr_url, json=payload, timeout=35)
            if res.status_code == 200:
                data = res.json()
                if data.get("status") == "ok":
                    return data["solution"]["response"]
                else:
                    print(f"[BW] FlareSolverr error status: {data.get('message')}")
        except Exception as e:
            print(f"[BW] FlareSolverr request failed for {url}: {e}")
        return None

    def destroy_session(self):
        """Clean up the FlareSolverr session when processing finishes."""
        payload = {"cmd": "sessions.destroy", "session": self.session_id}
        try:
            requests.post(self.flaresolverr_url, json=payload, timeout=5)
        except Exception:
            pass

    def tokenize(self, text: str) -> list[str]:
        text = text.lower()
        text = re.sub(r"[^a-z0-9\s]", " ", text)
        return [w for w in text.split() if w not in STOPWORDS and len(w) > 1]

    def fetch_isbn(self, title: str, volume: str) -> tuple[str | None, str] | None:
        """
        Extracts ISBN-13 and product URL from BookWalker NOVEL volume listings.
        Returns tuple of (cleaned_isbn, target_url/series_url) or None if no series match.
        """
        print(f"[BW] Searching BookWalker for: {title} Vol {volume}")

        clean_q = re.sub(r"[’':,\(\)]", "", title).strip()
        search_url = f"https://bookwalker.com/browse?search={quote_plus(clean_q)}"

        search_html = self.fetch_page_flaresolverr(search_url)
        if not search_html:
            return None

        soup = BeautifulSoup(search_html, "html.parser")

        # 1. Match NOVEL Series Links
        series_links = []
        for card in soup.select("div.book-card-grid-view-module__A8__ha__root, div[class*='book-card']"):
            label = card.select_one("p.text-module__BtXIkG__text, [class*='category'], [class*='label']")
            if not label or "NOVEL" not in label.get_text(strip=True).upper():
                continue

            a = card.select_one("a[href*='/series/']")
            if a and a.get("href"):
                href = a["href"]
                series_links.append(href if href.startswith("http") else f"https://bookwalker.com{href}")

        if not series_links:
            print("[BW] No NOVEL series links matched")
            return None

        series_url = series_links[0]
        series_html = self.fetch_page_flaresolverr(series_url)
        if not series_html:
            return None

        soup = BeautifulSoup(series_html, "html.parser")

        # 2. Verify Title Similarity
        series_title_el = (
            soup.select_one("p[class*='title-page']") or
            soup.select_one("h1") or
            soup.select_one("title")
        )
        series_title = series_title_el.get_text(strip=True) if series_title_el else ""
        series_title = series_title.split(" | BookWalker")[0].split(" (Light Novel)")[0]

        ln_clean = re.sub(r"[^\w\s]", "", title.lower()).strip()
        bw_clean = re.sub(r"[^\w\s]", "", series_title.lower()).strip()

        ln_tokens = self.tokenize(title)
        bw_tokens = self.tokenize(series_title)

        if not ln_tokens or not bw_tokens:
            return None

        # A. Exact normalized match (e.g. "GATE" == "GATE") -> Always accept
        if ln_clean == bw_clean:
            pass  # Matches perfectly
        else:
            # B. Calculate directional token coverage
            overlap = set(ln_tokens) & set(bw_tokens)
            coverage = len(overlap) / len(set(ln_tokens))

            # C. Guard against short/one-word false positives (e.g. "GATE" vs "Panguan: The Twelfth Gate")
            if len(ln_tokens) <= 2:
                # For short titles, reverse coverage matters too (prevents matching long titles containing the word)
                reverse_coverage = len(overlap) / len(set(bw_tokens))
                seq_ratio = SequenceMatcher(None, ln_clean, bw_clean).ratio()

                # Reject if reverse coverage is very low OR string similarity is low
                if reverse_coverage < 0.50 and seq_ratio < 0.70:
                    print(
                        f"[BW] Token match rejected for short title '{title}' vs '{series_title}' "
                        f"(rev_cov: {reverse_coverage:.2f}, seq_ratio: {seq_ratio:.2f})"
                    )
                    return None
            else:
                # Standard threshold for multi-word titles
                if coverage < 0.60:
                    print(f"[BW] Token coverage too low ({coverage:.2f}) for {title}")
                    return None

        # 3. Locate Target Volume Page
        volume_links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/de" in href or "/volume/" in href:
                volume_links.append(href if href.startswith("http") else f"https://bookwalker.com{href}")

        if not volume_links:
            return None, series_url

        vol_norm = str(volume).lower().strip()

        chosen_url = None
        if "." in vol_norm: # Fractional volume (e.g., 5.1, 7.5)
            base, frac = vol_norm.split(".", 1)
            base_forms = NUM_WORDS.get(base, [base])
            frac_forms = NUM_WORDS.get(frac, [frac])

            # Build regex component for base volume (e.g., "7", "seven", "vii", "ii")
            base_regex = "|".join(re.escape(b) for b in base_forms)
            
            # Build regex component for fractional part (e.g., "1", "one", "i")
            frac_regex = "|".join(re.escape(f) for f in frac_forms)

            # Split keywords including part, pt, act, volume, etc.
            keywords = ["part", "pt", "act", "episode", "side", "bonus"]
            kw_regex = "|".join(keywords)

            # Match patterns across link hrefs or aria-labels/text:
            # - Handles colons, dashes, spaces, e.g., "ii, part 1", "volume 7: part 1", "vol-13-act-1"
            target_pattern = (
                rf"(?:vol(?:ume)?[\s\-_:]*({base_regex})|({base_regex}))"  # Matches Vol 7 or II
                rf"[\s\-_:,]*"                                            # Optional colon, comma, space, dash
                rf"(?:({kw_regex})[\s\-_:]*)?"                           # Optional keyword like part/act/pt
                rf"({frac_regex})\b"                                     # Fractional number match
            )

            for a in soup.find_all("a", href=True):
                href = a["href"]
                if not ("/de" in href or "/volume/" in href):
                    continue

                full_url = href if href.startswith("http") else f"https://bookwalker.com{href}"
                
                # Check link URL slug as well as surrounding label/aria-label text
                aria_label = a.get("aria-label", "").lower()
                link_text = a.get_text(" ", strip=True).lower()
                combined_target = f"{href.lower()} {aria_label} {link_text}"

                if re.search(target_pattern, combined_target, re.IGNORECASE):
                    chosen_url = full_url
                    break
        else: # Whole number volume (e.g., 1, 2, 3)
            vol_clean = re.sub(r"(volume|vol\.?|\s)", "", vol_norm)
            target_pattern = rf"(-vol-|-volume-|-){re.escape(vol_clean)}\b|/de.*{re.escape(vol_clean)}"

            for link in volume_links:
                if re.search(target_pattern, link.lower()):
                    chosen_url = link
                    break

        # If specific fractional volume link wasn't found, return series URL
        if not chosen_url:
            print(f"[BW] Vol {volume} not found on series page. Falling back to series URL.")
            return None, series_url

        # 4. Parse Details Page for ISBN
        vol_html = self.fetch_page_flaresolverr(chosen_url)
        if not vol_html:
            return None, series_url

        vol_soup = BeautifulSoup(vol_html, "html.parser")
        text_content = vol_soup.get_text()

        isbn_match = re.search(r'ISBN\s*:?\s*(978[0-9\-]{10,14}|979[0-9\-]{10,14})', text_content, re.IGNORECASE)
        if isbn_match:
            cleaned = re.sub(r"[^0-9X]", "", isbn_match.group(1).upper())
            if len(cleaned) in (10, 13):
                return cleaned, chosen_url

        # Fall back to series URL if ISBN extraction fails on the volume page
        return None, series_url