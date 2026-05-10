import time
import re
from undetected_chromedriver import Chrome, ChromeOptions

class SevenSeasScraper:
    def __init__(self):
        opts = ChromeOptions()
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--window-size=1280,800")

        self.driver = Chrome(options=opts, headless=False)

    def get_cover(self, url: str) -> str | None:
        self.driver.get(url)
        time.sleep(3)

        html = self.driver.page_source

        # TODO: extract cover from inline JS once we see real HTML
        m = re.search(r'cover\s*:\s*"([^"]+)"', html)
        if m:
            return m.group(1)

        return None

    def close(self):
        self.driver.quit()

