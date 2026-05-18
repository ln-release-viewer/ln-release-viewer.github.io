from scrapers.yen_press_scraper import YenPressScraper
from scrapers.jnovel_scraper import JNovelScraper
from scrapers.bookwalker_scraper import BookWalkerScraper
from scrapers.seven_seas_scraper import SevenSeasScraper
from scrapers.crossinfinite_scraper import CrossInfiniteScraper
from scrapers.squareenix_scraper import SquareEnixScraper
from scrapers.generic_scraper import GenericScraper
from urllib.parse import quote_plus
from PIL import Image
import re

STOPWORDS = {"the", "a", "an", "of", "and", "to", "in", "on", "for"}
BOOKWALKER_ICON_PATTERNS = [
    "favicon", "apple-icon", "icon.png", "ogp", "default", "logo"
]

BOOKWALKER_PLACEHOLDER_PATTERNS = [
    "noimage", "comingsoon", "no-cover", "nocover", "placeholder"
]

def normalize_title(t: str) -> list[str]:
    t = t.lower()
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    return [w for w in t.split() if w]

def image_entropy(img: Image.Image) -> float:
    """Compute Shannon entropy of an image."""
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

class CoverScraper:
    def __init__(self, context):
        self.context = context

        # Scrapers
        self.bookwalker = BookWalkerScraper()
        self.yen = YenPressScraper()
        self.jnovel = JNovelScraper()
        self.seven = SevenSeasScraper()
        self.crossinf = CrossInfiniteScraper()
        self.squareenix = SquareEnixScraper()
        self.generic = GenericScraper()

    # ---------------------------------------------------------
    # BOOKWALKER SEARCH → FETCH → PARSE
    # ---------------------------------------------------------
    async def bookwalker_search_and_fetch(self, title: str, volume: str) -> str | None:
        print(f"[BW] Searching for: {title} Vol {volume}")

        # Normalize query
        q = (
            title.replace("’", "'")
                .replace(":", "")
                .replace(",", "")
                .replace("(", "")
                .replace(")", "")
                .strip()
        )
        q = quote_plus(title)
        search_url = f"https://bookwalker.com/browse?search={q}"
        print(f"[BW] Search URL: {search_url}")

        # Fetch search results
        search_html = await self.fetch_page(search_url)
        if not search_html:
            print("[BW] No search HTML")
            return None

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(search_html, "html.parser")

        # STEP 1 — Extract series links (Light Novel only)
        series_links = []
        for card in soup.select("div.book-card-grid-view-module__A8__ha__root"):
            # Check if this card is a NOVEL
            label = card.select_one("p.text-module__BtXIkG__text")
            if not label:
                continue
            if "NOVEL" not in label.get_text(strip=True).upper():
                continue

            # Extract the series link
            a = card.select_one("a[href*='/series/']")
            if a:
                series_links.append(a["href"])

        print(f"[BW] Series links found: {len(series_links)}")
        if not series_links:
            return None

        # Use the first LN series result
        series_url = "https://bookwalker.com" + series_links[0]
        print(f"[BW] Series URL: {series_url}")

        # STEP 2 — Fetch series page
        series_html = await self.fetch_page(series_url)
        if not series_html:
            print("[BW] No series HTML")
            return None

        soup = BeautifulSoup(series_html, "html.parser")

        # Extract series title
        # Extract series title using multiple fallback selectors
        series_title_el = (
            soup.select_one("p[class*='title-page']") or
            soup.select_one("p[class*='title']") or
            soup.select_one("[class*='series']") or
            soup.select_one("div[data-testid='series-title']") or
            soup.select_one("title")
        )

        series_title = ""
        if series_title_el:
            series_title = series_title_el.get_text(strip=True)
            # If we got the <title> tag, strip the " | BookWalker" suffix
            if " | BookWalker" in series_title:
                series_title = series_title.split(" | BookWalker")[0]

        print(f"[BW] Series page title: {series_title}")



        # Validate title similarity
        def tokenize(t: str) -> list[str]:
            t = t.lower()
            t = re.sub(r"[^a-z0-9\s]", " ", t)
            tokens = [w for w in t.split() if w not in STOPWORDS]
            return tokens

        ln_tokens = tokenize(title)
        bw_tokens = tokenize(series_title)

        ln_set = set(ln_tokens)
        bw_set = set(bw_tokens)

        overlap = ln_set & bw_set

        print(f"[BW] Token overlap: {overlap}")

        # 1. Require at least 2 meaningful tokens in common
        if len(overlap) < 2:
            print("[BW] Rejecting — insufficient token overlap")
            return None

        # 2. Require first token match (strong anchor)
        if ln_tokens[0] != bw_tokens[0]:
            print("[BW] Rejecting — first token mismatch")
            return None

        # 3. Require at least 50% of LN tokens to appear in BW tokens
        coverage = len(overlap) / len(ln_set)
        print(f"[BW] Coverage: {coverage:.2f}")

        if coverage < 0.90:
            print("[BW] Rejecting — insufficient coverage")
            return None

        print("[BW] Series accepted via token-based match")

        # STEP 3 — Extract volume links
        volume_links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/volume/" in href:
                volume_links.append(href)

        print(f"[BW] Volume links found: {len(volume_links)}")
        if not volume_links:
            print("[BW] No volumes found on BookWalker")
            return None

        # Normalize all slugs
        slugs = [v.lower() for v in volume_links]

        # Detect if series is numeric or title-based
        has_numbers = any(re.search(r"\d", s) for s in slugs)

        # Normalize LNRelease title for matching
        def slugify(t: str) -> str:
            t = t.lower()
            t = re.sub(r"[^a-z0-9]+", "-", t)
            return t.strip("-")

        title_slug = slugify(title)

        chosen = None

        # STEP 4A — Title-based matching (Rascal, Monogatari, Haruhi, etc.)
        if not has_numbers:
            print("[BW] Detected title-based series — matching by title slug")

            for s in slugs:
                if title_slug in s:
                    chosen = s
                    break

            if not chosen:
                print("[BW] No title-based match found")
                return None

        else:
            # STEP 4B — Numeric matching
            vol_norm = (
                volume.lower()
                    .replace("volume", "")
                    .replace("vol.", "")
                    .replace("vol", "")
                    .strip()
            )

            print(f"[BW] Normalized volume: {vol_norm}")

            patterns = []

            # Fractional volumes
            if "." in vol_norm:
                major, minor = vol_norm.split(".", 1)
                patterns += [
                    f"volume-{major}-part-{minor}",
                    f"volume-{major}-{minor}",
                    f"volume-{major}.{minor}",
                    f"volume-{major}_{minor}",
                    f"{major}-part-{minor}",
                    f"{major} part {minor}",
                ]
            else:
                patterns += [
                    f"volume-{vol_norm}",
                    f"-vol-{vol_norm}",
                    f"-volume-{vol_norm}",
                    f"-{vol_norm}",
                ]

            print(f"[BW] Volume patterns: {patterns}")

            for s in slugs:
                if any(p in s for p in patterns):
                    chosen = s
                    break

            # Fuzzy fallback
            if not chosen:
                major = vol_norm.split(".", 1)[0]
                for s in slugs:
                    if f"volume-{major}" in s:
                        chosen = s
                        break

            if not chosen:
                print("[BW] No numeric volume match found")
                return None

        # STEP 5 — Fetch volume page
        volume_url = "https://bookwalker.com" + chosen
        print(f"[BW] Volume URL: {volume_url}")

        volume_html = await self.fetch_page(volume_url)
        if not volume_html:
            print("[BW] No volume HTML")
            return None

        # STEP 6 — Parse cover with strict validation
        cover = self.bookwalker.parse(volume_html)
        if not cover:
            print("[BW] No valid cover found")
            return None

        # Reject icons or placeholders again (double safety)
        lc = cover.lower()
        if any(p in lc for p in BOOKWALKER_ICON_PATTERNS):
            print("[BW] Rejected icon masquerading as cover")
            return None

        if any(p in lc for p in BOOKWALKER_PLACEHOLDER_PATTERNS):
            print("[BW] Rejected placeholder cover")
            return None

        print(f"✔ BookWalker cover found for {title} Vol {volume}")
        return cover




    # ---------------------------------------------------------
    # PLAYWRIGHT FETCH
    # ---------------------------------------------------------
    async def fetch_page(self, url: str) -> str | None:
        page = await self.context.new_page()
        html = None

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)

            # BOOKWALKER hydration
            if "bookwalker.com" in url:
                try:
                    # Wait for React-rendered book cards or detail sections
                    await page.wait_for_selector(
                        "div.book-card-grid-view-module__A8__ha__root, "
                        "a[href*='/series/'], "
                        "a[href*='/volume/'], "
                        "p[class*='title-page']",
                        timeout=3000
                    )
                except:
                    pass

            # YEN PRESS hydration
            elif "yenpress.com" in url:
                try:
                    await page.wait_for_selector(
                        "img[src*='cover'], div[class*='BookDetail']",
                        timeout=3000
                    )
                except:
                    pass

            # J-NOVEL hydration (very light)
            elif "j-novel.club" in url:
                try:
                    await page.wait_for_selector(
                        "img, h1, picture",
                        timeout=2000
                    )
                except:
                    pass

            # GENERIC: no hydration needed
            else:
                await page.wait_for_timeout(200)

            html = await page.content()

        except Exception as e:
            print(f"⚠ Exception while fetching {url}: {e}")
            html = None

        finally:
            await page.close()

        return html


    async def get_cover(self, url: str, title: str = None, volume: str = None) -> str | None:
        # 1. Seven Seas (Selenium)
        if "sevenseasentertainment.com" in url:
            img = self.seven.get_cover(url)
            if img:
                print(f"✔ Seven Seas cover saved for {title} vol {volume}")
                return img

        html = await self.fetch_page(url)

        # 2. Yen Press - Note: Doesn't fall through to BookWalker - returns cover images
        if "yenpress.com" in url:
            img = self.yen.parse(html)
            if img and not is_placeholder_image(img):
                print(f"✔ Yen Press cover saved for {title} vol {volume}")
                return img

        # 3. J-Novel Club
        if "j-novel.club" in url and volume:
            img = await self.jnovel.parse(html, url=url, volume=volume)
            if img:
                print(f"✔ J-Novel Club cover saved for {title} vol {volume}")
                return img

        # 4. Cross Infinite World
        if "crossinfworld.com" in url:
            img = self.crossinf.parse(html, url=url)
            if img:
                print(f"✔ Cross Infinite World cover saved for {title} vol {volume}")
                return img

        # 5. Square Enix
        if "squareenixmangaandbooks.square-enix-games.com" in url:
            img = await self.squareenix.parse(html, url=url)
            if img:
                print(f"✔ Square Enix cover saved for {title} vol {volume}")
                return img

        # 6. BookWalker search fallback
        if title and volume:
            bw_cover = await self.bookwalker_search_and_fetch(title, volume)
            if bw_cover:
                return bw_cover

        # 8. Generic fallback
        return self.generic.parse(html, expected_title=title)
