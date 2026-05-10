import asyncio
import io
import json
import re
import time
from pathlib import Path
import hashlib
import requests
from PIL import Image
from playwright.async_api import async_playwright
from scrape_covers import CoverScraper

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "releases.json"
COVERS_DIR = ROOT / "public" / "covers"
COVERS_DIR.mkdir(parents=True, exist_ok=True)

REQUEST_DELAY = 0.4  # polite delay for HTTP APIs

STEALTH_JS = """
// navigator.webdriver
Object.defineProperty(navigator, 'webdriver', {
  get: () => false,
});

// plugins
Object.defineProperty(navigator, 'plugins', {
  get: () => [1, 2, 3],
});

// languages
Object.defineProperty(navigator, 'languages', {
  get: () => ['en-US', 'en'],
});

// WebGL vendor spoofing
const getParameter = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function(parameter) {
  if (parameter === 37445) return 'Intel Inc.';
  if (parameter === 37446) return 'Intel Iris OpenGL Engine';
  return getParameter(parameter);
};

// Chrome runtime
window.chrome = {
  runtime: {},
};

// Permissions
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
  parameters.name === 'notifications'
    ? Promise.resolve({ state: Notification.permission })
    : originalQuery(parameters)
);
"""


def slugify_short(title: str, volume: str) -> str:
    # Remove characters Windows can't handle
    safe = re.sub(r"[^a-zA-Z0-9\s-]", "", title.lower())

    # Keep first 6 words
    words = safe.split()
    short = "-".join(words[:6])

    # Hash full title for uniqueness
    h = hashlib.sha1(title.encode("utf-8")).hexdigest()[:6]

    return f"{short}-vol-{volume}-{h}"


def is_valid_image(content: bytes) -> bool:
    try:
        img = Image.open(io.BytesIO(content))
        w, h = img.size
        return w > 1 and h > 1
    except Exception:
        return False


def openlibrary_cover_url(isbn: str) -> str:
    return f"https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg"


def fetch_openlibrary_cover(isbn: str) -> bytes | None:
    if not isbn:
        return None
    time.sleep(REQUEST_DELAY)
    url = openlibrary_cover_url(isbn)
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return r.content
    except Exception:
        pass
    return None


def fetch_google_books_cover(isbn: str) -> bytes | None:
    if not isbn:
        return None
    time.sleep(REQUEST_DELAY)
    params = {"q": f"isbn:{isbn}"}
    try:
        r = requests.get(
            "https://www.googleapis.com/books/v1/volumes",
            params=params,
            timeout=10,
        )
        if r.status_code != 200:
            return None
        data = r.json()
        items = data.get("items") or []
        if not items:
            return None
        volume = items[0]
        info = volume.get("volumeInfo", {})
        links = info.get("imageLinks", {})
        thumb = links.get("thumbnail") or links.get("smallThumbnail")
        if not thumb:
            return None
        img = requests.get(thumb, timeout=10)
        if img.status_code == 200:
            return img.content
    except Exception:
        pass
    return None


async def scrape_all_publishers(releases: list[dict]) -> list[tuple[dict, str | None]]:
    results: list[tuple[dict, str | None]] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
        )

        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="en-US",
            timezone_id="America/New_York",
        )

        # Inject stealth patches
        await context.add_init_script(STEALTH_JS)

        scraper = CoverScraper(context)

        for r in releases:
            url = r.get("link")
            if not url:
                results.append((r, None))
                continue

            img_url = await scraper.get_cover(url)
            results.append((r, img_url))

        await context.close()
        await browser.close()

    return results


def main():
    with DATA_PATH.open("r", encoding="utf-8") as f:
        releases = json.load(f)

    # First pass: Open Library + Google Books
    for r in releases:
        title = r["title"]
        vol = r["volume"]
        isbn = r.get("isbn")
        slug = slugify_short(title, str(vol))
        cover_path = COVERS_DIR / f"{slug}.jpg"

        if r.get("cover") and cover_path.exists():
            print(f"Cover for {title} already exists. Continuing...")
            continue

        print(f"Fetching cover for {title} vol {vol} (ISBN {isbn})")

        img_content = None

        if isbn:
            img_content = fetch_openlibrary_cover(isbn)
            if img_content and is_valid_image(img_content):
                cover_path.write_bytes(img_content)
                r["cover"] = f"/covers/{slug}.jpg"
                print(f"✔ Open Library cover saved for {title} vol {vol}")
                continue
            else:
                print(f"Open Library failed for ISBN {isbn}, trying Google Books…")

            img_content = fetch_google_books_cover(isbn)
            if img_content and is_valid_image(img_content):
                cover_path.write_bytes(img_content)
                r["cover"] = f"/covers/{slug}.jpg"
                print(f"✔ Google Books cover saved for {title} vol {vol}")
                continue
            else:
                print(f"Google Books failed for ISBN {isbn}, will try publisher scrape later…")
        else:
            print(f"No ISBN for {title} vol {vol} — will try publisher scrape later…")

    # Second pass: Publisher scraping for anything still missing a cover
    missing = [r for r in releases if not r.get("cover") and r.get("link")]
    if missing:
        print("Starting publisher scraping pass…")
        publisher_results = asyncio.run(scrape_all_publishers(missing))

        for r, img_url in publisher_results:
            title = r["title"]
            vol = r["volume"]
            slug = slugify_short(title, str(vol))
            cover_path = COVERS_DIR / f"{slug}.jpg"

            if not img_url:
                print(f"❌ No publisher image URL for {title} vol {vol}")
                continue

            try:
                time.sleep(REQUEST_DELAY)
                resp = requests.get(img_url, timeout=10)
                if resp.status_code != 200:
                    print(f"❌ Failed to download publisher image for {title} vol {vol}")
                    continue

                content = resp.content
                if not is_valid_image(content):
                    print(f"❌ Invalid publisher image for {title} vol {vol}")
                    continue

                cover_path.write_bytes(content)
                r["cover"] = f"/covers/{slug}.jpg"
                print(f"✔ Publisher cover saved for {title} vol {vol}")
            except Exception:
                print(f"❌ Error downloading publisher image for {title} vol {vol}")

    # Write back updated JSON
    with DATA_PATH.open("w", encoding="utf-8") as f:
        json.dump(releases, f, ensure_ascii=False, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
