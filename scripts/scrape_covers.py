import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; LNReleaseBot/1.0)"
}

def fetch_html(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            return r.text
    except Exception:
        pass
    return None

def extract_og_image(html):
    soup = BeautifulSoup(html, "html.parser")
    tag = soup.find("meta", property="og:image")
    if tag and tag.get("content"):
        return tag["content"]
    return None

def scrape_seven_seas(url):
    html = fetch_html(url)
    if not html:
        return None
    return extract_og_image(html)

def scrape_yen_press(url):
    html = fetch_html(url)
    if not html:
        return None
    return extract_og_image(html)

def scrape_jnovel(url):
    html = fetch_html(url)
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")

    # JNC uses <img class="book-cover">
    img = soup.find("img", class_="book-cover")
    if img and img.get("src"):
        return img["src"]

    # fallback to og:image
    return extract_og_image(html)

def scrape_bookwalker(url):
    html = fetch_html(url)
    if not html:
        return None
    return extract_og_image(html)

def get_publisher_cover(url):
    """Route to the correct scraper based on domain."""
    if "sevenseasentertainment.com" in url:
        return scrape_seven_seas(url)
    if "yenpress.com" in url:
        return scrape_yen_press(url)
    if "j-novel.club" in url:
        return scrape_jnovel(url)
    if "bookwalker.com" in url:
        return scrape_bookwalker(url)

    # generic fallback
    html = fetch_html(url)
    if html:
        return extract_og_image(html)

    return None
