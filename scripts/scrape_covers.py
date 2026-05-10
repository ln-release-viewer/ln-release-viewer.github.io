from scrapers.yen_press_scraper import YenPressScraper
from scrapers.jnovel_scraper import JNovelScraper
from scrapers.bookwalker_scraper import BookWalkerScraper
from scrapers.seven_seas_scraper import SevenSeasScraper

class CoverScraper:
    def __init__(self, context):
        self.context = context
        self.yen = YenPressScraper()
        self.jnovel = JNovelScraper()
        self.bookwalker = BookWalkerScraper()
        self.seven = SevenSeasScraper()

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

        # fallback: OG image
        return extract_og_image(html)

