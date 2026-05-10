from scrapers.yen_press_scraper import YenPressScraper
from scrapers.jnovel_scraper import JNovelScraper
from scrapers.bookwalker_scraper import BookWalkerScraper
from scrapers.seven_seas_scraper import SevenSeasScraper
from scrapers.generic_scraper import GenericScraper

class CoverScraper:
    def __init__(self, context):
        self.context = context

        # Publisher-specific scrapers
        self.yen = YenPressScraper()
        self.jnovel = JNovelScraper()
        self.bookwalker = BookWalkerScraper()
        self.seven = SevenSeasScraper()

        # Fallback OG-image scraper
        self.generic = GenericScraper()

    async def fetch_page(self, url: str) -> str | None:
        page = await self.context.new_page()
        html = None

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)

            # --- Hydration waits (important for Yen Press) ---
            # Wait for Next.js hydration to finish
            try:
                await page.wait_for_function(
                    "() => window.__NEXT_DATA__ && window.__NEXT_DATA__.props",
                    timeout=5000
                )
            except:
                pass

            # Wait for any image that looks like a cover
            try:
                await page.wait_for_selector("img[src*='cover']", timeout=5000)
            except:
                pass

            # Give JS a little more time (Yen Press sometimes needs this)
            await page.wait_for_timeout(1000)

            html = await page.content()

            # --- Cloudflare detection ---
            if html and (
                "cf-browser-verification" in html
                or "Checking your browser" in html
                or "cf-challenge" in html
            ):
                print(f"⚠ Cloudflare challenge detected for: {url}")

                # Dump HTML for debugging
                debug_path = f"debug/debug_cloudflare_{_debug_slug(url)}.html"
                with open(debug_path, "w", encoding="utf-8") as f:
                    f.write(html)
                print(f"⚠ Saved Cloudflare debug HTML to {debug_path}")

            if not html or "cover" not in html:
                debug_path = f"debug/debug_{_debug_slug(url)}.html"
                with open(debug_path, "w", encoding="utf-8") as f:
                    f.write(html or "")
                print(f"⚠ Saved debug HTML to {debug_path}")


        except Exception as e:
            print(f"⚠ Exception while fetching {url}: {e}")
            html = None

        finally:
            await page.close()

        return html
        
    async def get_cover(self, url: str) -> str | None:
        # Seven Seas uses Selenium
        if "sevenseasentertainment.com" in url:
            return self.seven.get_cover(url)

        # Everything else uses Playwright
        html = await self.fetch_page(url)
        if not html:
            return None

        if "yenpress.com" in url:
            return self.yen.parse(html)
        if "j-novel.club" in url:
            return self.jnovel.parse(html)
        if "bookwalker.com" in url:
            return self.bookwalker.parse(html)

        # fallback
        return self.generic.parse(html)

