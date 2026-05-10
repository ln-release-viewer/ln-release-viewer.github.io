import time
import re
from undetected_chromedriver import Chrome, ChromeOptions

Path("debug").mkdir(exist_ok=True)

class SevenSeasScraper:
    def __init__(self):
        opts = ChromeOptions()
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--window-size=1280,800")

        # Force UDC to match GitHub Actions Chrome version
        self.driver = Chrome(options=opts, headless=False, version_main=147)

    def get_cover(self, url: str) -> str | None:
        self.driver.get(url)
        time.sleep(3)

        html = self.driver.page_source

        # Dump HTML for debugging
        slug = re.sub(r"[^a-zA-Z0-9-]", "-", url.lower())[:40]
        debug_path = f"debug/sevenseas_{slug}.html"
        with open(debug_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"⚠ Seven Seas debug saved to {debug_path}")

        # TODO: extract cover once we see real Seven Seas HTML
        m = re.search(r'cover\s*:\s*"([^"]+)"', html)
        if m:
            return m.group(1)

        return None

    def close(self):
        self.driver.quit()

