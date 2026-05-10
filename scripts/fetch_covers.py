import json
import re
import requests
from pathlib import Path
from io import BytesIO
from PIL import Image
import asyncio
from scrape_covers import CoverScraper
from playwright.async_api import async_playwright


RELEASES = Path("data/releases.json")
OUTPUT = Path("data/releases.json")
COVERS_DIR = Path("public/covers")
COVERS_DIR.mkdir(parents=True, exist_ok=True)

OPENLIB_URL = "https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg"
GOOGLE_BOOKS_URL = "https://www.googleapis.com/books/v1/volumes"

def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")

def is_valid_image(data: bytes) -> bool:
    """Reject 1×1 or corrupted images."""
    try:
        img = Image.open(BytesIO(data))
        w, h = img.size
        if w <= 2 and h <= 2:
            return False
        return True
    except Exception:
        return False

def fetch_openlib(isbn):
    url = OPENLIB_URL.format(isbn=isbn)
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200 and r.content:
            if is_valid_image(r.content):
                return r.content
    except Exception:
        pass
    return None

def fetch_google_books(isbn):
    params = {"q": f"isbn:{isbn}", "maxResults": 1}
    try:
        r = requests.get(GOOGLE_BOOKS_URL, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return None

    items = data.get("items")
    if not items:
        return None

    links = items[0].get("volumeInfo", {}).get("imageLinks", {})
    for key in ["extraLarge", "large", "medium", "thumbnail"]:
        url = links.get(key)
        if not url:
            continue
        try:
            img = requests.get(url, timeout=10).content
            if is_valid_image(img):
                return img
        except Exception:
            continue

    return None

async def scrape_all_publishers(releases):
    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        scraper = CoverScraper(browser)

        for r in releases:
            url = r.get("link")
            if not url:
                results.append((r, None))
                continue

            img_url = await scraper.get_cover(url)
            results.append((r, img_url))

        await browser.close()

    return results


def main():
    releases = json.loads(RELEASES.read_text())

    for r in releases:
        isbn = r.get("isbn")

        slug = slugify(f"{r['title']}-vol-{r['volume']}")
        cover_path = COVERS_DIR / f"{slug}.jpg"

        # Reuse existing cover
        if cover_path.exists():
            r["cover"] = f"/covers/{slug}.jpg"
            print(f"Already have cover for {r['title']} vol {r['volume']}")
            continue

        print(f"Fetching cover for {r['title']} vol {r['volume']} (ISBN {isbn})")

        # Try Open Library first
        if isbn:
            img = fetch_openlib(isbn)
            if img:
                cover_path.write_bytes(img)
                r["cover"] = f"/covers/{slug}.jpg"
                print(f"✔ Open Library cover saved for {r['title']} vol {r['volume']}")
                continue

        print(f"Open Library failed for ISBN {isbn}, trying Google Books…")

        # Fallback: Google Books
        if isbn:
            img = fetch_google_books(isbn)
            if img:
                cover_path.write_bytes(img)
                r["cover"] = f"/covers/{slug}.jpg"
                print(f"✔ Google Books cover saved for {r['title']} vol {r['volume']}")
                continue

        print(f"❌ No valid cover found for {r['title']} vol {r['volume']}")

        print(f"Google Books failed for ISBN {isbn}, trying publisher scrape…")

        # Fallback: Scrape Publisher
        print("Starting publisher scraping pass…")
        publisher_results = asyncio.run(scrape_all_publishers(releases))

        for r, img_url in publisher_results:
            isbn = r.get("isbn")
            slug = slugify(f"{r['title']}-vol-{r['volume']}")
            cover_path = COVERS_DIR / f"{slug}.jpg"

            if img_url:
                try:
                    img = requests.get(img_url, timeout=10).content
                    if is_valid_image(img):
                        cover_path.write_bytes(img)
                        r["cover"] = f"/covers/{slug}.jpg"
                        print(f"✔ Publisher cover saved for {r['title']} vol {r['volume']}")
                        continue
                except Exception:
                    pass

            print(f"❌ No valid cover found for {r['title']} vol {r['volume']}")


    OUTPUT.write_text(json.dumps(releases, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
