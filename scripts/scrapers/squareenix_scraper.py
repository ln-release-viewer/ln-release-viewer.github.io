import aiohttp
from bs4 import BeautifulSoup

class SquareEnixScraper:
    async def parse(self, html: str, url: str) -> str | None:
        soup = BeautifulSoup(html, "html.parser")

        # Find the portrait cover container
        cover_div = soup.find("div", class_=lambda c: c and "aspect-[2/3]" in c)
        if not cover_div:
            return None

        img = cover_div.find("img")
        if not img:
            return None

        src = img.get("src")
        if not src:
            return None

        # Square Enix URLs are absolute already
        return src
