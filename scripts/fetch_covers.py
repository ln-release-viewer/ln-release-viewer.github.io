import json
import re
import requests
from pathlib import Path

RELEASES = Path("data/releases.json")
OUTPUT = Path("data/releases.json")
COVERS_DIR = Path("public/covers")
COVERS_DIR.mkdir(parents=True, exist_ok=True)

GOOGLE_BOOKS_URL = "https://www.googleapis.com/books/v1/volumes"

def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")

def clean_title(title):
    # Remove punctuation that hurts Google Books search
    return re.sub(r"[^a-zA-Z0-9 ]+", "", title)

def search_google_books(title, publisher):
    title_clean = clean_title(title)

    # Best query pattern for LNs
    q = f'intitle:"{title_clean}" "{publisher}" "light novel"'

    params = {"q": q, "maxResults": 5}

    try:
        r = requests.get(GOOGLE_BOOKS_URL, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return None

    items = data.get("items")
    if not items:
        return None

    # Pick the first item with an image
    for item in items:
        info = item.get("volumeInfo", {})
        image_links = info.get("imageLinks")
        if image_links:
            return (
                image_links.get("extraLarge")
                or image_links.get("large")
                or image_links.get("medium")
                or image_links.get("thumbnail")
            )

    return None


def main():
    releases = json.loads(RELEASES.read_text())

    for r in releases:
        slug = slugify(f"{r['title']}-vol-{r['volume']}")
        cover_path = COVERS_DIR / f"{slug}.jpg"

        # If already downloaded, reuse it
        if cover_path.exists():
            r["cover"] = f"/covers/{slug}.jpg"
            continue

        # Search Google Books
        url = search_google_books(r["title"], r["volume"])
        if not url:
            continue

        # Download the image
        try:
            img = requests.get(url, timeout=10).content
            cover_path.write_bytes(img)
            r["cover"] = f"/covers/{slug}.jpg"
        except Exception:
            pass

    OUTPUT.write_text(json.dumps(releases, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()

