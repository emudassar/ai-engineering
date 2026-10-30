"""
main.py - the web API that the chat widget talks to.

Run it with:  uv run uvicorn app.main:app --port 8000

Endpoints:
  GET  /                  - the owner dashboard (dashboard/ folder)
  GET  /static/widget.js  - the chat widget the business pastes into its site
  POST /chat              - answer a visitor question
  POST /lead              - save a "please call me back" request
  /admin/...              - dashboard API, see admin.py
"""
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.admin import router as admin_router
from app.chat import answer_question
from app.config import PROJECT_DIR
from app.store import get_site, save_lead, setup_collection

setup_collection()

app = FastAPI(title="Local Biz Bot")

# The widget runs on the customer's domain and calls this API on ours, so the
# browser needs CORS permission. We allow every origin here and do the real
# per-site check in check_origin() below.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["POST"], allow_headers=["*"])

# Serve widget/widget.js at /static/widget.js and the dashboard at /dashboard/
app.mount("/static", StaticFiles(directory=PROJECT_DIR / "widget"), name="static")
app.mount("/dashboard", StaticFiles(directory=PROJECT_DIR / "dashboard", html=True), name="dashboard")
app.include_router(admin_router)


@app.get("/", include_in_schema=False)
def home():
    return RedirectResponse("/dashboard/")


# ---------------- Request bodies (validated by Pydantic) ----------------
class Message(BaseModel):
    role: Literal["user", "assistant"]  # visitors cannot send "system" messages
    content: str = Field(max_length=2000)


class ChatRequest(BaseModel):
    site_id: str
    message: str = Field(min_length=1, max_length=500)
    history: list[Message] = Field(default=[], max_length=6)  # last few messages


class LeadRequest(BaseModel):
    site_id: str
    name: str = Field(min_length=1, max_length=100)
    phone: str = Field(min_length=5, max_length=30)
    question: str = Field(default="", max_length=500)


# ---------------- Security check ----------------
def check_origin(request: Request, site_id):
    """Only the business's own website may use its site_id.

    Without this, anyone could copy the <script> snippet onto another site
    and spend our LLM budget.
    """
    site = get_site(site_id)
    if site is None:
        raise HTTPException(404, "Unknown site_id")
    allowed_origin, profile = site

    origin = request.headers.get("origin", "")
    if origin.replace("://www.", "://") != allowed_origin.replace("://www.", "://"):
        raise HTTPException(403, "This website is not allowed to use this chatbot")
    return profile


# ---------------- Endpoints ----------------
@app.post("/chat")
def chat(body: ChatRequest, request: Request):
    profile = check_origin(request, body.site_id)
    history = [m.model_dump() for m in body.history]
    return answer_question(profile, body.site_id, body.message, history)


@app.post("/lead")
def lead(body: LeadRequest, request: Request):
    check_origin(request, body.site_id)
    save_lead(body.site_id, body.name, body.phone, body.question)
    return {"ok": True}
