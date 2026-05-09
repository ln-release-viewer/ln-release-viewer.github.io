import csv
import json
import re
from pathlib import Path

RELEASES = Path("data/releases.json")
BOOKS_CSV = Path("lnrelease-src/books.csv")
OUTPUT = Path("data/releases.json")

FORMAT_PRIORITY = {
    "Paperback": 1,
    "Hardback": 1,
    "Hardcover": 1,
    "Physical": 1,
    "Digital": 2,
    "Ebook": 2,
    "Audiobook": 3,
}

def normalize_title(s):
    s = s.lower()
    s = re.sub(r"[^a-z0-9 ]+", "", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()

def load_books():
    books = []
    with BOOKS_CSV.open("r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 7:
                continue

            books.append({
                "serieskey": row[0],
                "link": row[1],
                "publisher": row[2],
                "title": row[3],
                "volume": row[4],
                "format": row[5],
                "isbn": row[6] or None,
                "date": row[7] if len(row) > 7 else None,
                "title_norm": normalize_title(row[3]),
            })
    return books

def main():
    releases = json.loads(RELEASES.read_text())
    books = load_books()

    for r in releases:
        r_title_norm = normalize_title(r["title"])
        r_volume = r["volume"].strip()

        # Find all matching entries
        matches = [
            b for b in books
            if b["title_norm"] == r_title_norm
            and b["volume"] == r_volume
        ]

        if matches:
            # Sort by format priority
            matches.sort(key=lambda b: FORMAT_PRIORITY.get(b["format"], 99))
            best = matches[0]
            r["isbn"] = best["isbn"]
        else:
            r["isbn"] = None

    OUTPUT.write_text(json.dumps(releases, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()


