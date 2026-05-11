import time
import re
from pathlib import Path
from undetected_chromedriver import Chrome, ChromeOptions
import re
from bs4 import BeautifulSoup

def parse(self, html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")

    # 1. OG image
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        return og["content"]

    # 2. WordPress post thumbnail
    thumb = soup.find("img", class_="attachment-post-thumbnail")
    if thumb and thumb.get("src"):
        return thumb["src"]

    # 3. Volume cover block
    vc = soup.select_one("#volume-cover img")
    if vc and vc.get("src"):
        return vc["src"]

    # 4. Any <img> that looks like a cover
    for img in soup.find_all("img"):
        src = img.get("src") or ""
        if any(k in src.lower() for k in ["cover", "volume", "vol", "jacket"]):
            return src

    return None

Path("debug").mkdir(exist_ok=True)

def slug_from_url(url: str) -> str:
    # Extract the last path segment
    m = re.search(r"/books/([^/]+)/?", url)
    if not m:
        return "unknown"

    slug = m.group(1).lower()
    slug = re.sub(r"[^a-z0-9-]", "-", slug)
    return slug[:80]


class SevenSeasScraper:
    def __init__(self):
        opts = ChromeOptions()
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--window-size=1280,800")

        # Force UDC to match GitHub Actions Chrome version
        self.driver = Chrome(options=opts, headless=False, version_main=147)

    def get_cover(self, url: str) -> str | None:
        # Create a fresh browser for every request
        opts = ChromeOptions()
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--window-size=1280,800")

        driver = Chrome(options=opts, headless=False, version_main=147)

        driver.get(url)
        time.sleep(4)

        html = driver.page_source

        slug = slug_from_url(url)
        debug_path = f"debug/sevenseas_{slug}.html"
        with open(debug_path, "w", encoding="utf-8") as f:
            f.write(html)

        driver.quit()

        # TODO: parse cover
        return self.parse(html)


    def close(self):
        self.driver.quit()

