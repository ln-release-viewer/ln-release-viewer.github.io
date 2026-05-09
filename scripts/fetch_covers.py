import json
import re
import requests
from pathlib import Path

RELEASES = Path("data/releases.json")
OUTPUT = Path("data/releases.json")
COVERS_DIR = Path("public/covers")
COVERS_DIR.mkdir(parents=True, exist_ok=True)

OPENLIB_URL = "https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg"

def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")

def fetch_cover(isbn):
    url = OPENLIB_URL.format(isbn=isbn)
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200 and r.content:
            return r.content
    except Exception:
        pass
    return None

def main():
    releases = json.loads(RELEASES.read_text())

    for r in releases:
        isbn = r.get("isbn")
        if not isbn:
            print(f"No ISBN for {r['title']} vol {r['volume']} — skipping")
            continue

        slug = slugify(f"{r['title']}-vol-{r['volume']}")
        cover_path = COVERS_DIR / f"{slug}.jpg"

        # Reuse existing cover
        if cover_path.exists():
            r["cover"] = f"/covers/{slug}.jpg"
            print(f"Already have cover for {r['title']} vol {r['volume']}")
            continue

        print(f"Fetching cover for {r['title']} vol {r['volume']} (ISBN {isbn})")

        img = fetch_cover(isbn)
        if not img:
            print(f"❌ No cover found for ISBN {isbn}")
            continue

        cover_path.write_bytes(img)
        r["cover"] = f"/covers/{slug}.jpg"
        print(f"✔ Saved cover: {cover_path}")

    OUTPUT.write_text(json.dumps(releases, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
