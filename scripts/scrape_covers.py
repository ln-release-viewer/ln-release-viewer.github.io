from scrapers.yen_press_scraper import YenPressScraper
from scrapers.jnovel_scraper import JNovelScraper
from scrapers.bookwalker_scraper import BookWalkerScraper
from scrapers.seven_seas_scraper import SevenSeasScraper
from scrapers.generic_scraper import GenericScraper

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
        # Normalize search query
        q = title.replace("’", "'").replace(":", "").replace(",", "")
        q = q.replace("(", "").replace(")", "")
        q = q.strip()

        search_url = f"https://bookwalker.com/search/?q={q.replace(' ', '+')}"

        # 1. Fetch search results page
        search_html = await self.fetch_page(search_url)
        if not search_html:
            return None

        # 2. Parse search results for volume links
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(search_html, "html.parser")

        # BookWalker search results use <a class="bw-book"> or <a class="item">
        candidates = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/volume/" in href:
                candidates.append(href)

        if not candidates:
            return None

        # 3. Try to match the correct volume number
        # BookWalker URLs often contain "...-vol-3" or "...-volume-3"
        vol = volume.lower().replace("volume", "").replace("vol.", "").replace("vol", "").strip()

        def matches_volume(url: str) -> bool:
            url_lower = url.lower()
            return f"-vol-{vol}" in url_lower or f"-volume-{vol}" in url_lower

        # Prefer exact volume match
        for c in candidates:
            if matches_volume(c):
                volume_url = "https://bookwalker.com" + c
                break
        else:
            # If no exact match, just take the first candidate
            volume_url = "https://bookwalker.com" + candidates[0]

        # 4. Fetch the BookWalker volume page
        volume_html = await self.fetch_page(volume_url)
        if not volume_html:
            return None

        # 5. Parse cover using BookWalkerScraper
        cover = self.bookwalker.parse(volume_html)
        if cover:
            print(f"✔ BookWalker cover found for {title} Vol {volume}")
            return cover

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

    # ---------------------------------------------------------
    # MAIN COVER PIPELINE
    # ---------------------------------------------------------
    async def get_cover(self, url: str, title: str = None, volume: str = None) -> str | None:
        # -----------------------------------------------------
        # 1. BOOKWALKER FIRST (search → volume → cover)
        # -----------------------------------------------------
        if title and volume:
            bw_cover = await self.bookwalker.search_and_fetch(title, volume)
            if bw_cover:
                return bw_cover

        # -----------------------------------------------------
        # 2. SEVEN SEAS (Selenium)
        # -----------------------------------------------------
        if "sevenseasentertainment.com" in url:
            return self.seven.get_cover(url)

        # -----------------------------------------------------
        # 3. PUBLISHER SCRAPING (Playwright)
        # -----------------------------------------------------
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

        # -----------------------------------------------------
        # 4. GENERIC OG-IMAGE FALLBACK
        # -----------------------------------------------------
        return self.generic.parse(html)


    async def get_cover(self, url: str) -> str | None:
        # -----------------------------------------
        # 1. BOOKWALKER FIRST
        # -----------------------------------------
        if "bookwalker.com" in url:
            html = await self.fetch_page(url)
            if html:
                img = self.bookwalker.parse(html)
                if img:
                    return img
            # If BookWalker URL fails, fall through to publishers

        # -----------------------------------------
        # 2. SEVEN SEAS (Selenium)
        # -----------------------------------------
        if "sevenseasentertainment.com" in url:
            return self.seven.get_cover(url)

        # -----------------------------------------
        # 3. PUBLISHERS (Playwright)
        # -----------------------------------------
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

        # -----------------------------------------
        # 4. FALLBACK: GENERIC OG-IMAGE SCRAPER
        # -----------------------------------------
        return self.generic.parse(html)

