"""
onboard.py - add a business website to the chatbot.

Usage:  uv run python -m app.onboard https://www.example-plumbing.com

It crawls the site, extracts the business profile, stores everything in
Qdrant, and prints the <script> snippet to paste into the website.
Run it again any time the website changes: it replaces the old data.
"""
import os
import sys
import time
from urllib.parse import urlparse

import httpx

from app.config import BACKEND_URL, qdrant
from app.crawl import crawl_site, make_chunks
from app.profile import extract_profile
from app.store import get_site, save_site, setup_collection


def make_site_id(url):
    """'https://www.joes-plumbing.com' -> 'joes-plumbing-com'"""
    host = urlparse(url).netloc.removeprefix("www.")
    return host.replace(".", "-").replace(":", "-")


def make_snippet(site_id):
    """The <script> tag the business pastes into its website."""
    return f'<script src="{BACKEND_URL}/static/widget.js" data-site="{site_id}" defer></script>'


def onboard(url, public_url=None):
    """Crawl, extract and save one website. Used by this CLI and by the dashboard.

    public_url: the address visitors use, when we crawl the site through another
    address (on Hugging Face we crawl localhost but visitors come from *.hf.space).
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("Enter a full website address, like https://example.com")

    url = url.rstrip("/") + "/"
    public = urlparse(public_url) if public_url else parsed
    site_id = make_site_id(public.geturl())
    origin = f"{public.scheme}://{public.netloc}"  # the only website allowed to use this bot

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


def onboard_space():
    """Hugging Face Spaces only: add the product website to its own chatbot.

    A free Space loses its disk on every restart, so without this the live demo
    would forget the site. Runs in a background thread once the server is up.
    """
    public_url = f"https://{os.environ['SPACE_HOST']}"
    local_url = f"http://localhost:{os.getenv('PORT', '7860')}"
    if get_site(make_site_id(public_url)) is not None:
        return  # already there (e.g. Qdrant Cloud is used)

    for _ in range(60):  # wait for uvicorn to start serving
        try:
            httpx.get(local_url, timeout=2)
            break
        except httpx.HTTPError:
            time.sleep(1)
    try:
        onboard(local_url, public_url=public_url)
        print(f"Onboarded {public_url}")
    except Exception as error:  # never crash the server because of this
        print(f"Could not onboard {public_url}: {error}")


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
