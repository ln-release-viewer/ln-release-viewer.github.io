import re
import json
import aiohttp
import os
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

SPLIT_KEYWORDS = ["part", "pt", "pt.", "act", "episode", "interlude", "side", "bonus"]
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

class JNovelScraper:
    async def _url_exists(self, url: str) -> bool:
        """Helper to verify image URL exists."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.head(url, timeout=5) as resp:
                    return resp.status == 200
        except Exception:
            return False

    async def parse(
        self, html: str, url: str = "", volume: float | int | str | None = None
    ) -> dict | None:
        soup = BeautifulSoup(html, "html.parser")
        vol_str = str(volume) if volume is not None else ""

        cover_url = None
        synopsis = None

        # Find the target volume container in HTML
        container = None

        # -----------------------------------------------------------------
        # 1. Standard & Heading-Based Volume Matching
        # -----------------------------------------------------------------
        if volume is not None and "." not in vol_str:
            containers = soup.find_all("div", id=re.compile(r"volume-\d+"))
            
            for c in containers:
                header = c.find(["h1", "h2", "h3", "h4", "h5", "h6"])
                if not header:
                    continue
                
                header_text = header.get_text(" ", strip=True).lower()
                
                # Use regex to match exact "volume 48" (avoiding matching "volume 48.5" or "volume 4")
                if re.search(rf"\bvolume\s+{re.escape(vol_str)}\b", header_text):
                    # Ensure it's not a bonus/part sub-volume unless explicitly requested
                    if not any(k in header_text for k in SPLIT_KEYWORDS):
                        container = c
                        break

            # Secondary fallback: Direct ID check if heading search didn't land
            if not container:
                container = soup.find("div", id=f"volume-{volume}")

        # -----------------------------------------------------------------
        # 2. Fractional Volume Matching (5.1 -> Volume 5 Pt. 1 / Part 1)
        # -----------------------------------------------------------------
        elif "." in vol_str:
            base, frac = vol_str.split(".", 1)
            containers = soup.find_all("div", id=re.compile(r"volume-(\d+)"))

            for c in containers:
                header = c.find("h2")
                if not header:
                    continue

                text = header.get_text(" ", strip=True).lower()
                if f"volume {base}" not in text:
                    continue

                # Ensure we match whole words using word boundaries (\b)
                has_keyword = any(re.search(rf"\b{re.escape(k)}\b", text) for k in SPLIT_KEYWORDS)
                if not has_keyword:
                    continue

                frac_forms = NUM_WORDS.get(frac, [frac])
                has_frac = any(re.search(rf"\b{re.escape(f)}\b", text) for f in frac_forms)
                if has_frac:
                    container = c
                    break

        # -----------------------------------------------------------------
        # 3. Extract Cover Image & Synopsis from DOM Container
        # -----------------------------------------------------------------
        if container:
            # --- Cover Extraction ---
            img = container.find("img")
            if img:
                src = img.get("src") or img.get("data-src")
                if src:
                    url_960 = src.replace("/240/", "/960/")
                    url_480 = src.replace("/240/", "/480/")
                    for candidate in (url_960, url_480, src):
                        if await self._url_exists(candidate):
                            cover_url = candidate
                            break

            # --- Synopsis Extraction ---
            # Grab all paragraph tags inside the container
            p_nodes = container.find_all("p")
            synopsis_parts = []
            for p in p_nodes:
                text = p.get_text(strip=True)
                if text and not text.startswith("Published") and not text.startswith("ISBN"):
                    synopsis_parts.append(text)

            if synopsis_parts:
                synopsis = "\n\n".join(synopsis_parts)

        # -----------------------------------------------------------------
        # 4. Fallback Cover via Meta Tag
        # -----------------------------------------------------------------
        if not cover_url:
            tag = soup.find("meta", property="og:image")
            if tag and tag.get("content"):
                cover_url = tag["content"]

        return {
            "cover_url": cover_url,
            "synopsis": synopsis
        }
