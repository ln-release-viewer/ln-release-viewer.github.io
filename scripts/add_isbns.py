import csv
import json
from pathlib import Path

RELEASES = Path("data/releases.json")
BOOKS_CSV = Path("lnrelease-src/books.csv")
OUTPUT = Path("data/releases.json")

def load_books():
    books = []
    with BOOKS_CSV.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            books.append({
                "title": row["name"].strip(),
                "volume": row["volume"].strip(),
                "isbn": row["isbn"].strip(),
                "publisher": row["publisher"].strip(),
            })
    return books

def normalize(s):
    return s.lower().replace("’", "'").strip()

def main():
    releases = json.loads(RELEASES.read_text())
    books = load_books()

    for r in releases:
        r_title = normalize(r["title"])
        r_volume = r["volume"].strip()

        # Try to find a matching book entry
        match = next(
            (
                b for b in books
                if normalize(b["title"]) == r_title
                and b["volume"] == r_volume
            ),
            None
        )

        if match:
            r["isbn"] = match["isbn"]
        else:
            r["isbn"] = None  # For debugging

    OUTPUT.write_text(json.dumps(releases, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
