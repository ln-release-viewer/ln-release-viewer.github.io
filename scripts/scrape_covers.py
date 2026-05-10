import json
import re
import requests
import time
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; LNReleaseBot/1.0)"
}

def fetch_html(url):
    try:
        time.sleep(0.4) # Limit requests
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

# -------------------------------
#  YEN PRESS (Next.js)
# -------------------------------
def scrape_yen_press(url):
    html = fetch_html(url)
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")
    script = soup.find("script", id="__NEXT_DATA__", type="application/json")
    if not script:
        return None

    try:
        data = json.loads(script.string)
        queries = data["props"]["pageProps"]["dehydratedState"]["queries"]
        for q in queries:
            cover = q["state"]["data"].get("cover")
            if cover:
                return cover
    except Exception:
        pass

    return extract_og_image(html)

# -------------------------------
#  SEVEN SEAS (Schema.org JSON)
# -------------------------------
def scrape_seven_seas(url):
    html = fetch_html(url)
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")
    ld_json = soup.find("script", type="application/ld+json")
    if ld_json:
        try:
            data = json.loads(ld_json.string)
            if isinstance(data, dict) and "image" in data:
                return data["image"]
        except Exception:
            pass

    return extract_og_image(html)

# -------------------------------
#  J-NOVEL CLUB (Nuxt.js)
# -------------------------------
def scrape_jnovel(url):
    html = fetch_html(url)
    if not html:
        return None

    # Try Nuxt.js JSON
    match = re.search(r"window\.__NUXT__\s*=\s*(\{.*?\});", html, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(1))
            volumes = data["state"]["data"].get("volumes", [])
            for v in volumes:
                if "cover" in v:
                    return v["cover"]
        except Exception:
            pass

    # Fallback: og:image
    return extract_og_image(html)

# -------------------------------
#  BOOKWALKER (Schema.org JSON)
# -------------------------------
def scrape_bookwalker(url):
    html = fetch_html(url)
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")
    ld_json = soup.find("script", type="application/ld+json")
    if ld_json:
        try:
            data = json.loads(ld_json.string)
            if isinstance(data, dict) and "image" in data:
                return data["image"]
        except Exception:
            pass

    return extract_og_image(html)

# -------------------------------
#  GENERIC FALLBACK
# -------------------------------
def scrape_generic(url):
    html = fetch_html(url)
    if not html:
        return None
    return extract_og_image(html)

# -------------------------------
#  ROUTER
# -------------------------------
def get_publisher_cover(url):
    if "yenpress.com" in url:
        return scrape_yen_press(url)
    if "sevenseasentertainment.com" in url:
        return scrape_seven_seas(url)
    if "j-novel.club" in url:
        return scrape_jnovel(url)
    if "bookwalker.com" in url:
        return scrape_bookwalker(url)

    return scrape_generic(url)

