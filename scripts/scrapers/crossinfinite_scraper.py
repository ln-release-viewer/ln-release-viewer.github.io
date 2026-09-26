from bs4 import BeautifulSoup
from urllib.parse import urljoin

class CrossInfiniteScraper:
    BASE = "https://crossinfworld.com/"

    def parse(self, html: str, url: str) -> dict:
        soup = BeautifulSoup(html, "html.parser")

        cover_url = None
        synopsis = None

        # 1. Primary Cover Extraction (col-sm-4)
        raw_img_src = None
        left_col = soup.find("div", class_="col-sm-4")
        if left_col:
            img = left_col.find("img")
            if img and img.get("src"):
                raw_img_src = img["src"]
                cover_url = urljoin(self.BASE, raw_img_src)

        # 2. Synopsis Extraction (col-sm-6)
        syn_col = soup.find("div", class_="col-sm-6")
        if syn_col:
            synopsis_parts = []
            for p in syn_col.find_all("p"):
                text = p.get_text(strip=True)
                if text:
                    synopsis_parts.append(text)
            if synopsis_parts:
                synopsis = "\n\n".join(synopsis_parts)

        return {
            "cover_url": cover_url,
            "synopsis": synopsis,
        }