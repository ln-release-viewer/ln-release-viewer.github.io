import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urljoin

class CrossInfiniteScraper:
    BASE = "https://crossinfworld.com/"

    def parse(self, html: str, url: str) -> str | None:
        soup = BeautifulSoup(html, "html.parser")

        # The cover is always inside the left column
        left_col = soup.find("div", class_="col-sm-4")
        if not left_col:
            return None

        img = left_col.find("img")
        if not img:
            return None

        src = img.get("src")
        if not src:
            return None

        # Convert relative → absolute
        full_url = urljoin(self.BASE, src)


        return full_url