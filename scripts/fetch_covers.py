import asyncio
import io
import json
import re
import time
import os
from pathlib import Path
import hashlib
import requests
from PIL import Image
import numpy as np
from playwright.async_api import async_playwright
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from scrape_covers import CoverScraper

ROOT = Path(__file__).resolve().parents[1]
TAG = None # 
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

def compute_hash(content: bytes) -> str:
    # Compute MD5 hash of raw byte data.
    return hashlib.md5(content).hexdigest()

def is_valid_image(content: bytes) -> bool:
    try:
        img = Image.open(io.BytesIO(content))
        w, h = img.size
        return w > 1 and h > 1
    except Exception:
        return False

def is_placeholder_url(url: str) -> bool:
    url = url.lower()
    return any(x in url for x in [
        "coming-soon",
        "nocover",
        "noimage",
        "placeholder",
        "default",
        "temp",
    ])

def image_entropy(img: Image.Image) -> float:
    # Compute Shannon entropy of an image.
    if img.mode != "RGB":
        img = img.convert("RGB")

    histogram = np.array(img.histogram())
    histogram = histogram / histogram.sum()
    histogram = histogram[histogram > 0]

    return -np.sum(histogram * np.log2(histogram))

def is_placeholder_image(content: bytes) -> bool:
    try:
        img = Image.open(io.BytesIO(content)).convert("RGB")

        ent = image_entropy(img)
        uniq = len(img.getcolors(maxcolors=256*256*256) or [])
        var = np.array(img.convert("L")).var()

        print(f"[IMG] Entropy={ent:.2f}, UniqueColors={uniq}, Variance={var:.0f}")

        # Strongest signals first
        if uniq < 8000:
            return True
        if var < 1000:
            return True

        # Entropy is weakest, but still useful
        if ent < 3.0:
            return True

        return False

    except Exception as e:
        print(f"[IMG] Error checking entropy: {e}")
        return False

def download_image_with_flaresolverr(
    img_url: str, 
    session_id: str = "seven_seas_session", 
    flaresolverr_url: str | None = None
) -> bytes | None:
    """Fetches raw image bytes using a warm FlareSolverr session and extracted clearance cookies."""
    endpoint = (
        flaresolverr_url
        or os.getenv("FLARESOLVERR_URL")
        or "http://localhost:8191/v1"
    )
    
    # 1. Ask FlareSolverr to solve/reuse cookies using the shared session_id
    payload = {
        "cmd": "request.get",
        "url": img_url,
        "session": session_id,
        "maxTimeout": 15000
    }
    
    try:
        res = requests.post(endpoint, json=payload, timeout=20)
        if res.status_code != 200:
            return None
            
        data = res.json()
        if data.get("status") == "ok":
            solution = data.get("solution", {})
            
            # Extract Cloudflare clearance cookies and user-agent cached in FlareSolverr
            cookies = {c["name"]: c["value"] for c in solution.get("cookies", [])}
            user_agent = solution.get("userAgent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
            
            headers = {
                "User-Agent": user_agent,
                "Referer": "https://sevenseasentertainment.com/",
                "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
            }
            
            # Fast binary fetch directly via requests using extracted Cloudflare cookies
            img_res = requests.get(img_url, headers=headers, cookies=cookies, timeout=15)
            if img_res.status_code == 200:
                return img_res.content
            else:
                print(f"⚠️ Direct image download returned HTTP {img_res.status_code} for {img_url}")

    except requests.exceptions.ConnectionError:
        print(f"⚠️ FlareSolverr is unreachable at {endpoint}. Check Docker networking.")
    except Exception as e:
        print(f"⚠️ FlareSolverr image fetch error for {img_url}: {e}")
        
    return None

def normalize_vendor_url(url: str, amazon_tag: str | None = None) -> str:
    # Strips third-party tracking tags
    if not url:
        return url

    parsed = urlparse(url)
    query_params = parse_qs(parsed.query)

    # 1. Handle Amazon specific URL parameters
    if "amazon.com" in parsed.netloc or "amzn.to" in parsed.netloc:
        # Strip existing affiliate/tracking parameters
        for param in ["tag", "ref", "ref_", "ascsubtag"]:
            query_params.pop(param, None)
        if amazon_tag:
            query_params["tag"] = [amazon_tag]

    # 2. General tracking param cleanup for all vendors (UTM, etc.)
    for param in ["utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"]:
        query_params.pop(param, None)

    # Reconstruct the cleaned URL
    cleaned_query = urlencode(query_params, doseq=True)
    return urlunparse(parsed._replace(query=cleaned_query))


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


async def scrape_all_publishers(releases: list[dict]) -> list[tuple[dict, dict | str | None]]:
    results: list[tuple[dict, dict | str | None]] = []

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

        await context.add_init_script(STEALTH_JS)

        scraper = CoverScraper(context)

        for r in releases:
            url = r.get("link")
            if not url:
                results.append((r, None))
                continue

            data = await scraper.get_cover(
                url,
                title=r.get("title"),
                volume=r.get("volume")
            )

            results.append((r, data))

        await context.close()
        await browser.close()

    return results

def main():
    with DATA_PATH.open("r", encoding="utf-8") as f:
        releases = json.load(f)

    # FIRST PASS: Publisher scraping
    targets = [r for r in releases if r.get("link")]
    if targets:
        print("Starting publisher scraping pass…")
        publisher_results = asyncio.run(scrape_all_publishers(targets))

        for r, res in publisher_results:
            title = r["title"]
            vol = r["volume"]
            slug = slugify_short(title, str(vol))
            cover_path = COVERS_DIR / f"{slug}.jpg"

            # 1. Normalize response from scrapers
            if isinstance(res, dict):
                img_url = res.get("cover_url")
                synopsis = res.get("synopsis")
            elif isinstance(res, str):
                img_url = res
                synopsis = None
            else:
                img_url, synopsis = None, None

            # --- 1b. INTERCEPT 404 / MISSING PRODUCT PAGES ---
            if img_url == "404_NOT_FOUND":
                print(f"🚫 404 / Missing product page detected for {title} vol {vol}")
                r["is404"] = True
                r["cover"] = None
                r["synopsis"] = None
                continue  # Skip to next release, bypassing image downloads & ISBN pass

            # 2. Assign / Update Synopsis (Non-destructive)
            if synopsis and isinstance(synopsis, str) and synopsis.strip():
                clean_synopsis = synopsis.strip()
                existing_synopsis = r.get("synopsis")

                if existing_synopsis != clean_synopsis:
                    r["synopsis"] = clean_synopsis
                    if existing_synopsis:
                        print(f"📝 Updated synopsis for {title} vol {vol}")
                    else:
                        print(f"📝 Added new synopsis for {title} vol {vol}")
                else:
                    print(f"⏩ Unchanged synopsis for {title} vol {vol}")
            else:
                # Do NOT overwrite existing valid synopses if scraping returned None/empty
                if r.get("synopsis"):
                    print(f"⚠️ Scraper returned empty synopsis; retaining existing synopsis for {title} vol {vol}")
                else:
                    r["synopsis"] = None

            # 3. Handle Cover Image Download & Hash Logic
            if not img_url:
                print(f"❌ No publisher image URL for {title} vol {vol}")
                continue

            try:
                time.sleep(REQUEST_DELAY)
                
                # Direct FlareSolverr download with warm session
                if "sevenseasentertainment.com" in img_url:
                    content = download_image_with_flaresolverr(img_url, session_id="seven_seas_session")
                else:
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                        "Referer": "https://sevenseasentertainment.com/"
                    }
                    resp = requests.get(img_url, headers=headers, timeout=10)
                    content = resp.content if resp.status_code == 200 else None

                if not content or not is_valid_image(content):
                    print(f"❌ Invalid or failed image download (Cloudflare block?) for {title} vol {vol}")
                    continue

                if is_placeholder_url(img_url) or is_placeholder_image(content):
                    print(f"❌ Placeholder image detected for {title} vol {vol}")
                    continue

                # Compute hash
                new_hash = compute_hash(content)
                existing_hash = r.get("coverHash")

                if existing_hash and existing_hash == new_hash and cover_path.exists():
                    print(f"⏩ Unchanged cover artwork for {title} vol {vol}")
                else:
                    cover_path.write_bytes(content)
                    r["cover"] = f"/covers/{slug}.jpg"
                    r["coverHash"] = new_hash
                    print(f"✔ Saved/Updated cover for {title} vol {vol} (hash: {new_hash[:8]})")

            except Exception as e:
                print(f"❌ Error processing publisher image for {title} vol {vol}: {e}")

    # SECOND PASS: ISBN APIs (Open Library -> Google Books)
    for r in releases:
        if r.get("cover"):
            continue  # Already handled by publisher pass

        title = r["title"]
        vol = r["volume"]
        isbn = r.get("isbn")
        slug = slugify_short(title, str(vol))
        cover_path = COVERS_DIR / f"{slug}.jpg"

        if not isbn:
            print(f"No ISBN for {title} vol {vol} — skipping ISBN APIs")
            continue

        print(f"Trying ISBN APIs for {title} vol {vol} (ISBN {isbn})")

        # --- Open Library ---
        img_content = fetch_openlibrary_cover(isbn)
        if img_content and is_valid_image(img_content):
            cover_path.write_bytes(img_content)
            r["cover"] = f"/covers/{slug}.jpg"
            r["coverHash"] = compute_hash(img_content)  # Fixed missing variable
            print(f"✔ Open Library cover saved for {title} vol {vol}")
            continue

        # --- Google Books ---
        img_content = fetch_google_books_cover(isbn)
        if img_content and is_valid_image(img_content):
            cover_path.write_bytes(img_content)
            r["cover"] = f"/covers/{slug}.jpg"
            r["coverHash"] = compute_hash(img_content)  # Fixed missing variable
            print(f"✔ Google Books cover saved for {title} vol {vol}")
            continue

        print(f"❌ ISBN APIs failed for {title} vol {vol}")

    # BACKFILL HASHES
    for r in releases:
        if r.get("cover") and not r.get("coverHash"):
            slug = slugify_short(r["title"], str(r["volume"]))
            cover_path = COVERS_DIR / f"{slug}.jpg"
            if cover_path.exists():
                r["coverHash"] = compute_hash(cover_path.read_bytes())
                print(f"🛠 Backfilled hash for {r['title']} vol {r['volume']}")

    # WRITE UPDATED JSON
    with DATA_PATH.open("w", encoding="utf-8") as f:
        json.dump(releases, f, ensure_ascii=False, indent=2)
        f.write("\n")

    # CLEANUP OLD COVERS
    valid_filenames = {f"{slugify_short(r['title'], str(r['volume']))}.jpg" for r in releases}
    for filename in os.listdir(COVERS_DIR):
        if filename != "placeholder.jpg" and filename not in valid_filenames:
            try:
                os.remove(COVERS_DIR / filename)
                print(f"✔ Removed old cover: {filename}")
            except Exception as e:
                print(f"⚠ Failed to remove {filename}: {e}")

if __name__ == "__main__":
    main()
