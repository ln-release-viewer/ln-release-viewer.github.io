import asyncio
import re
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Browser, BrowserContext, Page


class AmazonProvider:
    def __init__(self, headless: bool = True):
        self.headless = headless
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    async def _init_browser(self):
        if not self._browser:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=self.headless)
            self._context = await self._browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 800},
            )
            self._page = await self._context.new_page()

    def sanitize_query(self, title: str, volume: str) -> str:
        main_title = re.split(r"[:\-\u2013\u2014]", title)[0]
        cleaned = re.sub(r"[^a-zA-Z0-9\s]", "", main_title)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return f"{cleaned} Volume {volume} light novel"

    def _clean_isbn(self, raw: str | None) -> str | None:
        if not raw:
            return None
        cleaned = re.sub(r"[^0-9X]", "", str(raw).upper())
        return cleaned if len(cleaned) in (10, 13) else None

    async def fetch_isbn(self, title: str, volume: str) -> str | None:
        await self._init_browser()
        query = self.sanitize_query(title, volume)
        search_url = f"https://www.amazon.com/s?k={quote_plus(query)}"

        try:
            await self._page.goto(search_url, wait_until="domcontentloaded", timeout=15000)

            selectors = [
                "div[data-component-type='s-search-result'] h2 a.a-link-normal",
                "a.a-link-normal.s-line-clamp-2",
                "h2 a.a-link-normal",
            ]

            link_element = None
            for selector in selectors:
                try:
                    link_element = await self._page.wait_for_selector(selector, timeout=2000)
                    if link_element:
                        break
                except Exception:
                    continue

            if link_element:
                href = await link_element.get_attribute("href")
                if href:
                    full_link = f"https://www.amazon.com{href}" if href.startswith("/") else href
                    await self._page.goto(full_link, wait_until="domcontentloaded", timeout=15000)

            await self._page.evaluate("window.scrollBy(0, 1000)")
            await asyncio.sleep(1)

            content = await self._page.content()
            soup = BeautifulSoup(content, "html.parser")
            body_text = re.sub(r"[\u200e\u200f\s]+", " ", soup.get_text())

            containers = [
                soup.find("div", id="detailBullets_feature_div"),
                soup.find("div", id="detailBulletsWrapper_feature_div"),
                soup.find("div", id="productDetails_db_sections"),
                soup.find("table", id="productDetails_techSpec_section_1"),
            ]

            for container in containers:
                if container:
                    text = re.sub(r"[\u200e\u200f\s]+", " ", container.get_text())

                    match13 = re.search(r"ISBN-?13\s*:\s*(978[-0-9\s]{10,17}|979[-0-9\s]{10,17})", text, re.IGNORECASE)
                    if match13:
                        cleaned = self._clean_isbn(match13.group(1))
                        if cleaned:
                            return cleaned

                    match10 = re.search(r"ISBN-?10\s*:\s*([0-9X-]{10,15})", text, re.IGNORECASE)
                    if match10:
                        cleaned = self._clean_isbn(match10.group(1))
                        if cleaned:
                            return cleaned

            match_global = re.search(r"ISBN-?13\s*:\s*(978[-0-9]{10,14}|979[-0-9]{10,14})", body_text, re.IGNORECASE)
            if match_global:
                return self._clean_isbn(match_global.group(1))

            bare_match = re.search(r"\b(978[0-9]{10}|979[0-9]{10})\b", re.sub(r"[-–]", "", body_text))
            if bare_match:
                return bare_match.group(1)

        except Exception as e:
            print(f" ⚠️ Playwright error during Amazon lookup: {e}")

        return None

    async def close(self):
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._browser = None
        self._playwright = None