"""
profile.py - extract the key business facts into a fixed structure.

Phone, hours, prices and service areas are the most-asked questions, and
getting them wrong costs the business customers. So instead of hoping the
vector search finds them, we extract them ONCE into a Pydantic model and
give the whole profile to the LLM with every question.
"""
import json

from pydantic import BaseModel

from app.config import LLM_MODEL, groq_client


# ---------------- The profile structure ----------------
class DayHours(BaseModel):
    day: str    # "monday"
    open: str   # "08:00" (24-hour clock)
    close: str  # "18:00"


class PriceItem(BaseModel):
    item: str        # "Drain cleaning"
    price: str       # "$129" - copied exactly as written on the site
    source_url: str  # page where the price appears


class BusinessProfile(BaseModel):
    name: str = ""
    phone: str = ""
    email: str = ""
    address: str = ""
    timezone: str = ""  # e.g. "America/Chicago", used to answer "are you open now?"
    service_areas: list[str] = []
    services: list[str] = []
    hours: list[DayHours] = []  # closed days are simply left out
    prices: list[PriceItem] = []


# ---------------- Extraction with the LLM ----------------
# Pages whose URL contains one of these words usually hold the key facts.
KEY_PAGE_WORDS = ["contact", "about", "service", "pricing", "price", "hours", "area", "location"]

EXTRACT_PROMPT = """You extract facts about a local business from its website.
Rules:
- Use ONLY information written in the website text. Never guess or invent.
- Leave a field empty ("" or []) if the website does not state it.
- Copy prices exactly as written, with the URL of the page they appear on.
- Hours use a 24-hour clock ("08:00"). Leave out days the business is closed.
- timezone: the IANA time zone of the business address (e.g. "America/Chicago"), or "" if there is no address.
Reply with JSON matching this schema:
{schema}"""


def pick_key_pages(pages):
    """The homepage plus pages that look like contact/services/pricing pages."""
    key_pages = [pages[0]]
    for page in pages[1:]:
        if any(word in page["url"].lower() for word in KEY_PAGE_WORDS):
            key_pages.append(page)
    return key_pages[:6]


def extract_profile(pages):
    key_pages = pick_key_pages(pages)

    # Build the LLM input: each page's text (shortened) with its URL.
    website_text = "\n\n".join(f"PAGE: {p['url']}\n{p['text'][:3000]}" for p in key_pages)

    # Phone/email links found in the HTML are reliable hints.
    phones = {phone for p in pages for phone in p["phones"]}
    emails = {email for p in pages for email in p["emails"]}
    hints = f"Phone links found: {sorted(phones)}\nEmail links found: {sorted(emails)}"

    response = groq_client.chat.completions.create(
        model=LLM_MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": EXTRACT_PROMPT.format(schema=json.dumps(BusinessProfile.model_json_schema()))},
            {"role": "user", "content": f"{hints}\n\n{website_text}"},
        ],
    )
    # Validate the LLM output against the model. Bad JSON raises an error here.
    return BusinessProfile.model_validate_json(response.choices[0].message.content)
