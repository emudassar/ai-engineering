"""
crawl.py - download a website and turn its pages into clean text chunks.

Steps:
  1. Find the page URLs (from sitemap.xml, or links on the homepage).
  2. Download each page.
  3. Remove scripts and menus, keep the readable text.
  4. Split the text into small chunks for the vector database.
"""
import re
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.config import CHUNK_WORDS, MAX_PAGES

HEADERS = {"User-Agent": "LocalBizBot/0.1 (website assistant)"}

# Common sitemap locations. WordPress uses the last two.
SITEMAP_PATHS = ["/sitemap.xml", "/sitemap_index.xml", "/wp-sitemap.xml"]


# ---------------- 1. Find page URLs ----------------
def same_site(url, base_url):
    """True if url is on the same website as base_url (www. ignored)."""
    host = urlparse(url).netloc.removeprefix("www.")
    return host == urlparse(base_url).netloc.removeprefix("www.")


def read_sitemap(client, sitemap_url, depth=0):
    """Return the <loc> URLs in a sitemap. A sitemap index lists more sitemaps, so we open those once."""
    try:
        resp = client.get(sitemap_url)
    except httpx.HTTPError:
        return []
    if resp.status_code != 200 or "<loc>" not in resp.text:
        return []

    locs = re.findall(r"<loc>\s*(.*?)\s*</loc>", resp.text)
    if "<sitemapindex" in resp.text and depth == 0:
        urls = []
        for child_sitemap in locs:
            urls += read_sitemap(client, child_sitemap, depth=1)
        return urls
    return locs


def links_on_homepage(client, base_url):
    """Fallback when there is no sitemap: every same-site link on the homepage."""
    resp = client.get(base_url)
    soup = BeautifulSoup(resp.text, "html.parser")
    urls = [base_url]
    for a in soup.find_all("a", href=True):
        url = urljoin(base_url, a["href"]).split("#")[0]
        if same_site(url, base_url) and url not in urls:
            urls.append(url)
    return urls


def find_page_urls(client, base_url):
    for path in SITEMAP_PATHS:
        urls = read_sitemap(client, urljoin(base_url, path))
        if urls:
            return urls
    return links_on_homepage(client, base_url)


# ---------------- 2 + 3. Download and clean pages ----------------
def clean_page(html):
    """Return the readable text of a page, plus phone numbers and emails from its links."""
    soup = BeautifulSoup(html, "html.parser")

    # Site owners can hide parts of a page from the bot (e.g. example mockups) with data-nobot.
    for tag in soup.select("[data-nobot]"):
        tag.decompose()

    # tel: and mailto: links are the most reliable contact details, so grab them first.
    phones = [a["href"][4:].strip() for a in soup.select('a[href^="tel:"]')]
    emails = [a["href"][7:].split("?")[0].strip() for a in soup.select('a[href^="mailto:"]')]

    # Remove things that are not readable content.
    for tag in soup(["script", "style", "noscript", "svg", "iframe", "nav"]):
        tag.decompose()

    text = re.sub(r"\s+", " ", soup.get_text(" ")).strip()
    return text, phones, emails


def crawl_site(base_url):
    """Download up to MAX_PAGES pages. Returns a list of {"url", "text", "phones", "emails"}."""
    pages = []
    with httpx.Client(headers=HEADERS, timeout=15, follow_redirects=True) as client:
        for url in find_page_urls(client, base_url):
            if len(pages) >= MAX_PAGES:
                break
            if not same_site(url, base_url):
                continue
            try:
                resp = client.get(url)
            except httpx.HTTPError:
                continue
            # Skip errors and non-HTML files (images, PDFs).
            if resp.status_code != 200 or "text/html" not in resp.headers.get("content-type", ""):
                continue

            text, phones, emails = clean_page(resp.text)
            if text:
                pages.append({"url": url, "text": text, "phones": phones, "emails": emails})
                print(f"  crawled {url}")
    return pages


# ---------------- 4. Split into chunks ----------------
def make_chunks(pages):
    """Split every page into chunks of CHUNK_WORDS words.

    Headers and footers repeat on every page, so identical chunks are kept only once.
    """
    chunks, seen = [], set()
    for page in pages:
        words = page["text"].split()
        for start in range(0, len(words), CHUNK_WORDS):
            text = " ".join(words[start:start + CHUNK_WORDS])
            if text not in seen:
                seen.add(text)
                chunks.append({"url": page["url"], "text": text})
    return chunks
