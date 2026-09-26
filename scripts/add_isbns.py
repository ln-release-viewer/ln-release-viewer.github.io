import csv
import json
import re
import time
import asyncio
import requests
from pathlib import Path
from urllib.parse import quote_plus
from scrapers.scrape_bookwalker_isbns import BookWalkerProvider
from scrapers.scrape_amazon_isbns import AmazonProvider

RELEASES = Path("data/releases.json")
BOOKS_CSV = Path("lnrelease-src/books.csv")
OUTPUT = Path("data/releases.json")

HEADERS = {
    "User-Agent": "LNReleaseViewer/1.0 (https://github.com/ln-release-viewer)"
}

FORMAT_PRIORITY = {
    "Paperback": 1,
    "Hardback": 1,
    "Hardcover": 1,
    "Physical": 1,
    "Digital": 2,
    "Ebook": 2,
    "Audiobook": 3,
}


def normalize_title(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9 ]+", "", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def clean_isbn(raw: str | None) -> str | None:
    if not raw:
        return None
    cleaned = re.sub(r"[^0-9X]", "", str(raw).upper())
    return cleaned if len(cleaned) in (10, 13) else None


def clean_title_words(text: str) -> set[str]:
    """Extract significant lowercase alphanumeric words (3+ chars)."""
    words = re.findall(r"\b[a-z0-9]{3,}\b", text.lower())
    # Exclude common noise words in light novel titles
    stop_words = {"vol", "volume", "light", "novel", "another", "world"}
    return {w for w in words if w not in stop_words}

def fetch_isbn_from_open_library(title: str, volume: str) -> str | None:
    # Do NOT split by colon - keep "Fanbook" or sub-series markers intact
    clean_search_title = re.sub(r"[^\w\s]", " ", title)
    clean_search_title = re.sub(r"\s+", " ", clean_search_title).strip()
    
    # Target title field directly in query
    query = f'title:"{clean_search_title}" {volume}'
    url = f"https://openlibrary.org/search.json?q={quote_plus(query)}&fields=title,isbn&limit=5"

    target_words = clean_title_words(title)
    volume_str = str(volume).strip()
    is_manga_target = "manga" in title.lower()

    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        
        if r.status_code == 200:
            data = r.json()
            for doc in data.get("docs", []):
                doc_title = doc.get("title", "")
                isbns = doc.get("isbn", [])

                if not isbns or not doc_title:
                    continue

                doc_title_lower = doc_title.lower()

                # 1. Reject Manga if target is Light Novel (and vice-versa)
                if not is_manga_target and "manga" in doc_title_lower:
                    continue

                # 2. Strict Keyword Match: Ensure ALL key target words exist in returned title
                doc_words = set(re.findall(r"\b[a-z0-9]{3,}\b", doc_title_lower))
                if target_words and not target_words.issubset(doc_words):
                    continue

                # 3. Verify volume number matches exact word boundary
                vol_pattern = rf"\b(vol|volume|part|\b)?\s*{re.escape(volume_str)}\b"
                if not re.search(vol_pattern, doc_title_lower):
                    continue

                # 4. Return preferred 13-digit ISBN
                for isbn in isbns:
                    cleaned = re.sub(r"[^0-9X]", "", str(isbn).upper())
                    if cleaned.startswith(("978", "979")) and len(cleaned) == 13:
                        return cleaned
                
                # Fallback to 10/13 digit clean string
                for isbn in isbns:
                    cleaned = re.sub(r"[^0-9X]", "", str(isbn).upper())
                    if len(cleaned) in (10, 13):
                        return cleaned

        elif r.status_code == 429:
            print(f" ⚠️ Open Library rate limited (429) for: {title} Vol {volume}")

    except requests.exceptions.Timeout:
        print(f" ⏱ Open Library timeout (10s) for: {title} Vol {volume}")
    except Exception as e:
        print(f" ⚠ Open Library error for {title} Vol {volume}: {e}")

    return None


def fetch_isbn_from_google_books(title: str, volume: str, publisher: str = "") -> str | None:
    """Flexible Google Books search without strict string quotation constraints."""
    # Try a natural query string first
    queries = [
        f"{title} Volume {volume} {publisher} light novel",
        f"{title} Vol {volume}",
    ]

    for query in queries:
        params = {"q": query, "maxResults": 3}
        try:
            time.sleep(0.3)
            r = requests.get("https://www.googleapis.com/books/v1/volumes", params=params, headers=HEADERS, timeout=5)
            if r.status_code != 200:
                continue

            data = r.json()
            items = data.get("items") or []

            for item in items:
                volume_info = item.get("volumeInfo", {})
                industry_ids = volume_info.get("industryIdentifiers", [])

                # Look for ISBN_13 first, then ISBN_10
                for identifier in industry_ids:
                    if identifier.get("type") == "ISBN_13":
                        return clean_isbn(identifier.get("identifier"))

                for identifier in industry_ids:
                    if identifier.get("type") == "ISBN_10":
                        return clean_isbn(identifier.get("identifier"))

        except Exception as e:
            print(f"⚠ Google Books API lookup failed for {title} Vol {volume}: {e}")

    return None


async def main():
    releases = json.loads(RELEASES.read_text(encoding="utf-8"))

    books = []
    if BOOKS_CSV.exists():
        with BOOKS_CSV.open("r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) < 7:
                    continue
                books.append({
                    "title_norm": normalize_title(row[3]),
                    "volume": row[4].strip(),
                    "format": row[5],
                    "isbn": clean_isbn(row[6]),
                })

    updated_count = 0
    # Instantiate once outside the loop to keep the FlareSolverr session warm
    bw = BookWalkerProvider()
    amazon_provider = AmazonProvider()

    try:
        for r in releases:
            if r.get("isbn"):
                continue  # Keep existing ISBN if present

            r_title_norm = normalize_title(r["title"])
            r_volume = str(r["volume"]).strip()
            fetched_isbn = None  # Reset variable for each iteration

            # Step 1: Check books.csv
            matches = [
                b for b in books
                if b["title_norm"] == r_title_norm and b["volume"] == r_volume and b["isbn"]
            ]

            if matches:
                matches.sort(key=lambda b: FORMAT_PRIORITY.get(b["format"], 99))
                r["isbn"] = matches[0]["isbn"]
                updated_count += 1
                print(f"✔ Matched ISBN from CSV for {r['title']} Vol {r_volume}: {r['isbn']}")
                continue

            # Step 2: Attempt BookWalker metadata fetch
            try:
                bw_res = bw.fetch_isbn(r["title"], r_volume)
                if bw_res:
                    fetched_isbn, bw_url = bw_res

                    # Ensure vendors list exists and store the BookWalker link
                    if "vendors" not in r or not isinstance(r["vendors"], list):
                        r["vendors"] = []

                    # Avoid duplicate entries if BookWalker is already present
                    if not any(v.get("name", "").lower() == "bookwalker" for v in r["vendors"]):
                        r["vendors"].append({
                            "name": "BookWalker",
                            "url": bw_url
                        })

                    # Only update ISBN and skip remaining lookup steps if we got an actual ISBN
                    if fetched_isbn:
                        r["isbn"] = fetched_isbn
                        updated_count += 1
                        print(f"✔ Fetched ISBN & vendor link via BookWalker for {r['title']} Vol {r_volume}: {r['isbn']}")
                        continue
                    else:
                        print(f"Found BookWalker series link for {r['title']} Vol {r_volume}, but no specific volume ISBN. Continuing to fallback providers...")

            except Exception as e:
                print(f"⚠️ BookWalker fetch failed for {r['title']} Vol {r_volume}: {e}")

            # Step 3: Amazon Playwright Scrape Fallback
            if not fetched_isbn:
                try:
                    fetched_isbn = await amazon_provider.fetch_isbn(r["title"], r_volume)
                    if fetched_isbn:
                        r["isbn"] = fetched_isbn
                        updated_count += 1
                        print(f"✔ Fetched ISBN via Amazon for {r['title']} Vol {r_volume}: {r['isbn']}")
                except Exception as e:
                    print(f"⚠️ Amazon fetch failed for {r['title']} Vol {r_volume}: {e}")

            # Step 4: Google Books API Fallback
            if not fetched_isbn:
                fetched_isbn = fetch_isbn_from_google_books(r["title"], r_volume, r.get("publisher", ""))
            
            # Step 4: Fallback to Open Library Search
            if not fetched_isbn:
                fetched_isbn = fetch_isbn_from_open_library(r["title"], r_volume)

            if fetched_isbn:
                r["isbn"] = fetched_isbn
                updated_count += 1
                print(f"✔ Fetched ISBN via API for {r['title']} Vol {r_volume}: {fetched_isbn}")
            else:
                r["isbn"] = None

    finally:
        # Clean up session when finished
        bw.destroy_session()
        await amazon_provider.close()

    OUTPUT.write_text(json.dumps(releases, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nFinished processing ISBNs. {updated_count} ISBNs added/updated.")


if __name__ == "__main__":
    asyncio.run(main())
