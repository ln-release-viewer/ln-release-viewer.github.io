from bs4 import BeautifulSoup

class HanashiScraper:
    def parse(self, html: str, url: str) -> str | None:
        soup = BeautifulSoup(html, "html.parser")

        # 1. Look for the new API-based cover endpoint
        for img in soup.find_all("img"):
            src = img.get("src")
            if src and "store-api.hanashi.media/ebooks/cover" in src:
                return src

        # 2. Fallback: any <img> with wp-content/uploads (older pages)
        for img in soup.find_all("img"):
            src = img.get("src")
            if src and "wp-content/uploads" in src:
                return src

        return None
