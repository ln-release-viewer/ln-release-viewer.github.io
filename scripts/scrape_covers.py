from scrapers.yen_press_scraper import YenPressScraper
from scrapers.jnovel_scraper import JNovelScraper
from scrapers.bookwalker_scraper import BookWalkerScraper
from scrapers.seven_seas_scraper import SevenSeasScraper
from scrapers.generic_scraper import GenericScraper

class CoverScraper:
    def __init__(self, context):
        self.context = context

        # Scrapers
        self.bookwalker = BookWalkerScraper()   # NOW FIRST
        self.yen = YenPressScraper()
        self.jnovel = JNovelScraper()
        self.seven = SevenSeasScraper()
        self.generic = GenericScraper()

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

            # Cloudflare detection
            if html and (
                "cf-browser-verification" in html
                or "Checking your browser" in html
                or "cf-challenge" in html
            ):
                print(f"⚠ Cloudflare challenge detected for: {url}")
                debug_path = f"debug/debug_cloudflare_{_debug_slug(url)}.html"
                with open(debug_path, "w", encoding="utf-8") as f:
                    f.write(html)

            if not html or "cover" not in html:
                debug_path = f"debug/debug_{_debug_slug(url)}.html"
                with open(debug_path, "w", encoding="utf-8") as f:
                    f.write(html or "")

        except Exception as e:
            print(f"⚠ Exception while fetching {url}: {e}")
            html = None

        finally:
            await page.close()

        return html

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

