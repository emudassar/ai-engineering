"""
admin.py - API for the owner dashboard (dashboard/ folder).

Every route here needs the X-Admin-Key header to match ADMIN_KEY in .env,
because these routes can crawl websites (costs LLM money) and show leads
(visitors' phone numbers).
"""
import os
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.chat import answer_question
from app.onboard import make_snippet, onboard
from app.store import count_chunks, get_site, list_leads, list_sites


# ---------------- Admin key check ----------------
def require_admin(x_admin_key: str = Header(default="")):
    admin_key = os.getenv("ADMIN_KEY", "")
    if not admin_key:
        raise HTTPException(503, "Set ADMIN_KEY in your .env file to use the dashboard")
    # compare_digest takes the same time for any wrong key, so the key can't be guessed by timing
    if not secrets.compare_digest(x_admin_key, admin_key):
        raise HTTPException(401, "Wrong admin key")


router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])


# ---------------- Request bodies ----------------
class NewSite(BaseModel):
    url: str = Field(min_length=4, max_length=300)


class Message(BaseModel):
    role: str
    content: str


class TestChat(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    history: list[Message] = Field(default=[], max_length=6)


# ---------------- Helpers ----------------
def site_details(site_id):
    """Everything the dashboard shows for one website."""
    site = get_site(site_id)
    if site is None:
        raise HTTPException(404, "Website not found")
    origin, profile = site
    return {
        "site_id": site_id,
        "origin": origin,
        "profile": profile.model_dump(),
        "chunk_count": count_chunks(site_id),
        "lead_count": len(list_leads(site_id)),
        "snippet": make_snippet(site_id),
    }


# ---------------- Routes ----------------
@router.get("/sites")
def all_sites():
    return list_sites()


@router.post("/sites")
def add_site(body: NewSite):
    """Crawl a website and build its bot. Takes 20-60 seconds. Running it again refreshes the data."""
    try:
        site_id = onboard(body.url.strip())
    except ValueError as error:
        raise HTTPException(400, str(error))
    return site_details(site_id)


@router.get("/sites/{site_id}")
def one_site(site_id: str):
    return site_details(site_id)


@router.get("/sites/{site_id}/leads")
def site_leads(site_id: str):
    return list(reversed(list_leads(site_id)))  # newest first


@router.post("/sites/{site_id}/chat")
def test_chat(site_id: str, body: TestChat):
    """Same answers as the real widget, but without the website origin check, so the owner can test."""
    site = get_site(site_id)
    if site is None:
        raise HTTPException(404, "Website not found")
    history = [{"role": m.role, "content": m.content} for m in body.history if m.role in ("user", "assistant")]
    return answer_question(site[1], site_id, body.message, history)
