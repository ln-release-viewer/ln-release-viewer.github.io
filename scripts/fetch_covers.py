import json
import re
import requests
from pathlib import Path

RELEASES = Path("data/releases.json")
OUTPUT = Path("data/releases.json")
COVERS_DIR = Path("public/covers")
COVERS_DIR.mkdir(parents=True, exist_ok=True)

ANILIST_URL = "https://graphql.anilist.co"

QUERY = """
query ($search: String, $volume: Int) {
  Media(search: $search, type: MANGA) {
    id
    title {
      romaji
      english
    }
    coverImage {
      large
      extraLarge
    }
  }
}
"""

def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")

def fetch_cover(title, volume):
    variables = {"search": title, "volume": int(float(volume)) if volume.replace(".", "", 1).isdigit() else None}
    response = requests.post(ANILIST_URL, json={"query": QUERY, "variables": variables})
    data = response.json()

    media = data.get("data", {}).get("Media")
    if not media:
        return None

    return media["coverImage"]["extraLarge"] or media["coverImage"]["large"]

def main():
    releases = json.loads(RELEASES.read_text())

    for r in releases:
        slug = slugify(f"{r['title']}-vol-{r['volume']}")
        cover_path = COVERS_DIR / f"{slug}.jpg"

        if cover_path.exists():
            r["cover"] = f"/covers/{slug}.jpg"
            continue

        url = fetch_cover(r["title"], r["volume"])
        if not url:
            continue

        img = requests.get(url).content
        cover_path.write_bytes(img)
        r["cover"] = f"/covers/{slug}.jpg"

    OUTPUT.write_text(json.dumps(releases, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
