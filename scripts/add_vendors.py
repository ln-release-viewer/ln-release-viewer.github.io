import json
import re
import asyncio
import aiohttp
from pathlib import Path
from urllib.parse import quote_plus
from scrapers.scrape_bookwalker_isbns import BookWalkerProvider

DATA_PATH = Path("data/releases.json")

# Custom User-Agent to avoid bot blocking on storefront checks
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def generate_candidate_vendors(title: str, volume: str, isbn: str | None, publisher: str) -> list[dict]:
    """Generates candidate vendor link structures for validation."""
    clean_title = re.sub(r"[^\w\s-]", "", title).strip()
    slug_title = re.sub(r"\s+", "-", clean_title.lower())
    clean_isbn = re.sub(r"[^0-9X]", "", str(isbn).upper()) if isbn else None
    
    pub = publisher.lower()
    candidates = []

    # 1. Amazon (Search Query Strategy)
    amazon_query = f"{title} volume {volume} light novel"
    candidates.append({
        "name": "Amazon",
        "url": f"https://www.amazon.com/s?k={quote_plus(amazon_query)}"
    })

    # 2. Apple Books (Direct ISBN Lookup)
    if clean_isbn:
        candidates.append({
            "name": "Apple Books",
            "url": f"https://books.apple.com/us/book/isbn{clean_isbn}"
        })

    # 3. Barnes & Noble (Direct ISBN Lookup)
    if clean_isbn:
        candidates.append({
            "name": "Barnes & Noble",
            "url": f"https://www.barnesandnoble.com/s/{clean_isbn}"
        })

    # 4. Kobo (Slug-Based Resolution)
    kobo_slug = f"{slug_title}-vol-{volume}"
    candidates.append({
        "name": "Kobo",
        "url": f"https://www.kobo.com/us/en/ebook/{kobo_slug}"
    })

    # 5. Books-A-Million (Physical Retailer - Direct ISBN)
    if clean_isbn and not any(p in pub for p in ["j-novel", "hanashi"]):
        candidates.append({
            "name": "Books-A-Million",
            "url": f"https://www.booksamillion.com/p/{clean_isbn}"
        })

    return candidates


async def validate_vendor_link(session: aiohttp.ClientSession, vendor: dict) -> dict | None:
    """
    Validates that a vendor URL resolves properly.
    Returns the vendor object if valid, otherwise None.
    """
    url = vendor["url"]
    
    # Amazon search pages & standard search queries always return 200 OK
    if "amazon.com/s?" in url:
        return vendor

    try:
        # First attempt lightweight HEAD request
        async with session.head(url, headers=HEADERS, timeout=5, allow_redirects=True) as resp:
            if resp.status == 200:
                return vendor
            
            # If HEAD returns 405 (Method Not Allowed) or 403, fallback to GET
            if resp.status in (403, 405):
                async with session.get(url, headers=HEADERS, timeout=5, allow_redirects=True) as get_resp:
                    if get_resp.status == 200:
                        return vendor

    except Exception:
        pass

    return None


def fetch_bookwalker_link_sync(bw: BookWalkerProvider, title: str, volume: str) -> str | None:
    """Helper to execute synchronous BookWalker FlareSolverr lookup in an async executor."""
    try:
        res = bw.fetch_isbn(title, volume)
        if res:
            isbn, bw_url = res
            return bw_url  # Returns valid series_url or volume_url
    except Exception as e:
        print(f"⚠️ BookWalker vendor lookup failed for {title} Vol {volume}: {e}")
    return None


# Create a semaphore to limit concurrent FlareSolverr requests
bw_semaphore = asyncio.Semaphore(1)  # Only 1 BookWalker lookup at a time


async def process_release_vendors(session: aiohttp.ClientSession, release: dict, bw: BookWalkerProvider, sem: asyncio.Semaphore) -> dict:
    if release.get("is404"):
        return release

    raw_existing = release.get("vendors") or []

    existing_vendors = []
    if isinstance(raw_existing, dict):
        for k, v in raw_existing.items():
            existing_vendors.append({"name": k.title(), "url": v})
    elif isinstance(raw_existing, list):
        for v in raw_existing:
            if isinstance(v, dict) and "name" in v and "url" in v:
                existing_vendors.append(v)

    existing_names = {v["name"].lower() for v in existing_vendors}

    publisher = release.get("publisher", "")
    title = release.get("title", "")
    volume = str(release.get("volume", ""))
    isbn = release.get("isbn")

    # Step 1: Throttle BookWalker lookups using the Semaphore
    if "bookwalker" not in existing_names:
        async with sem:  # Ensures only 1 task accesses FlareSolverr at a time
            loop = asyncio.get_running_loop()
            bw_url = await loop.run_in_executor(None, fetch_bookwalker_link_sync, bw, title, volume)
            if bw_url:
                existing_vendors.append({"name": "BookWalker", "url": bw_url})
                existing_names.add("bookwalker")

    # Step 2: Validate other candidate vendors concurrently
    candidates = generate_candidate_vendors(title, volume, isbn, publisher)
    new_candidates = [c for c in candidates if c["name"].lower() not in existing_names]

    tasks = [validate_vendor_link(session, candidate) for candidate in new_candidates]
    validated_results = await asyncio.gather(*tasks)

    for vendor in validated_results:
        if vendor:
            existing_vendors.append(vendor)

    release["vendors"] = existing_vendors[:6]
    return release


async def main():
    if not DATA_PATH.exists():
        print("releases.json not found.")
        return

    with DATA_PATH.open("r", encoding="utf-8") as f:
        releases = json.load(f)

    print("🔍 Validating vendor URLs across releases...")
    
    bw = BookWalkerProvider()
    bw_semaphore = asyncio.Semaphore(1)  # Throttle FlareSolverr
    conn = aiohttp.TCPConnector(limit=10)

    try:
        async with aiohttp.ClientSession(connector=conn) as session:
            updated_releases = await asyncio.gather(
                *[process_release_vendors(session, r, bw, bw_semaphore) for r in releases]
            )

        with DATA_PATH.open("w", encoding="utf-8") as f:
            json.dump(updated_releases, f, ensure_ascii=False, indent=2)
            f.write("\n")

        print(f"✔ Vendor processing complete. Updated {len(updated_releases)} releases.")

    finally:
        bw.destroy_session()


if __name__ == "__main__":
    asyncio.run(main())