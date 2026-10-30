"""
onboard.py - add a business website to the chatbot.

Usage:  uv run python -m app.onboard https://www.example-plumbing.com

It crawls the site, extracts the business profile, stores everything in
Qdrant, and prints the <script> snippet to paste into the website.
Run it again any time the website changes: it replaces the old data.
"""
import sys
from urllib.parse import urlparse

from app.config import BACKEND_URL, qdrant
from app.crawl import crawl_site, make_chunks
from app.profile import extract_profile
from app.store import save_site, setup_collection


def make_site_id(url):
    """'https://www.joes-plumbing.com' -> 'joes-plumbing-com'"""
    host = urlparse(url).netloc.removeprefix("www.")
    return host.replace(".", "-").replace(":", "-")


def make_snippet(site_id):
    """The <script> tag the business pastes into its website."""
    return f'<script src="{BACKEND_URL}/static/widget.js" data-site="{site_id}" defer></script>'


def onboard(url):
    """Crawl, extract and save one website. Used by this CLI and by the dashboard."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("Enter a full website address, like https://example.com")

    url = url.rstrip("/") + "/"
    site_id = make_site_id(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"  # the only website allowed to use this bot

    print(f"1/3 Crawling {url}")
    pages = crawl_site(url)
    if not pages:
        raise ValueError("No pages found on that website. Check the address.")
    chunks = make_chunks(pages)
    print(f"    {len(pages)} pages, {len(chunks)} chunks")

    print("2/3 Extracting business profile")
    profile = extract_profile(pages)

    print("3/3 Saving to Qdrant")
    setup_collection()
    save_site(site_id, origin, profile, chunks)
    return site_id


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: uv run python -m app.onboard <website-url>")
    try:
        new_site_id = onboard(sys.argv[1])
    except ValueError as error:
        sys.exit(str(error))
    print("\nDone! Paste this before </body> on the website:\n")
    print(make_snippet(new_site_id))
    qdrant.close()
