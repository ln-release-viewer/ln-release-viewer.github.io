from scrapers.yen_press_scraper import YenPressScraper
from scrapers.jnovel_scraper import JNovelScraper
from scrapers.bookwalker_scraper import BookWalkerScraper
from scrapers.seven_seas_scraper import SevenSeasScraper
from scrapers.generic_scraper import GenericScraper
from urllib.parse import quote_plus

class CoverScraper:
    def __init__(self, context):
        self.context = context

        # Scrapers
        self.bookwalker = BookWalkerScraper()   # FIRST PRIORITY
        self.yen = YenPressScraper()
        self.jnovel = JNovelScraper()
        self.seven = SevenSeasScraper()
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

        # STEP 3 — Extract volume links
        volume_links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/volume/" in href:
                volume_links.append(href)

        print(f"[BW] Volume links found: {len(volume_links)}")
        if not volume_links:
            return None

        # STEP 4 — Match correct volume
        vol_norm = (
            volume.lower()
                .replace("volume", "")
                .replace("vol.", "")
                .replace("vol", "")
                .strip()
        )

        print(f"[BW] Normalized volume: {vol_norm}")

        patterns = []

        # Fractional volume handling
        if "." in vol_norm:
            major, minor = vol_norm.split(".", 1)

            # Most common BookWalker pattern
            patterns.append(f"volume-{major}-part-{minor}")

            # Sometimes BookWalker uses hyphen
            patterns.append(f"volume-{major}-{minor}")

            # Sometimes BookWalker uses dot
            patterns.append(f"volume-{major}.{minor}")

            # Sometimes BookWalker uses underscore
            patterns.append(f"volume-{major}_{minor}")

            # Sometimes BookWalker uses "part X"
            patterns.append(f"{major}-part-{minor}")

            # Sometimes BookWalker uses "X part Y"
            patterns.append(f"{major} part {minor}")

        else:
            # Normal integer volume
            patterns.append(f"volume-{vol_norm}")
            patterns.append(f"-vol-{vol_norm}")
            patterns.append(f"-volume-{vol_norm}")
            patterns.append(f"-{vol_norm}")

        print(f"[BW] Volume patterns: {patterns}")

        def matches(url: str) -> bool:
            u = url.lower()
            return any(p in u for p in patterns)

        chosen = None
        for v in volume_links:
            if matches(v):
                chosen = v
                break

        # Fuzzy fallback: look for major volume number
        if not chosen:
            major = vol_norm.split(".", 1)[0]
            for v in volume_links:
                if f"volume-{major}" in v.lower():
                    chosen = v
                    break

        # Final fallback
        if not chosen:
            chosen = volume_links[0]

        volume_url = "https://bookwalker.com" + chosen
        print(f"[BW] Volume URL: {volume_url}")


        # STEP 5 — Fetch volume page
        volume_html = await self.fetch_page(volume_url)
        if not volume_html:
            print("[BW] No volume HTML")
            return None

        # STEP 6 — Parse cover
        cover = self.bookwalker.parse(volume_html)
        if cover:
            print(f"✔ BookWalker cover found for {title} Vol {volume}")
            return cover

        print("[BW] No cover found")
        return None



    # ---------------------------------------------------------
    # PLAYWRIGHT FETCH
    # ---------------------------------------------------------
    async def fetch_page(self, url: str) -> str | None:
        page = await self.context.new_page()
        html = None

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)

            # Hydration waits (Yen Press)
            try:
                await page.wait_for_function(
                    "() => window.__NEXT_DATA__ && window.__NEXT_DATA__.props",
                    timeout=5000
                )
            except:
                pass

            try:
                await page.wait_for_selector("img[src*='cover']", timeout=5000)
            except:
                pass

            await page.wait_for_timeout(1000)
            html = await page.content()

        except Exception as e:
            print(f"⚠ Exception while fetching {url}: {e}")
            html = None

        finally:
            await page.close()

        return html

    async def get_cover(self, url: str, title: str = None, volume: str = None) -> str | None:
        # 1. BookWalker search
        if title and volume:
            bw_cover = await self.bookwalker_search_and_fetch(title, volume)
            if bw_cover:
                return bw_cover

        # 2. Seven Seas
        if "sevenseasentertainment.com" in url:
            return self.seven.get_cover(url)

        # 3. Publisher scraping
        html = await self.fetch_page(url)
        if not html:
            return None

        if "yenpress.com" in url:
            img = self.yen.parse(html)
            if img:
                return img

        if "j-novel.club" in url:
            img = self.jnovel.parse(html)
            if img:
                return img

        if "bookwalker.com" in url:
            img = self.bookwalker.parse(html)
            if img:
                return img

        # 4. Generic fallback
        return self.generic.parse(html)

