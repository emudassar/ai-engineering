"""
index.py - Vercel's entry point for the API.

Vercel runs this file as a Python serverless function. vercel.json sends
/chat, /lead and /admin/... here; the website in public/ is served by
Vercel's CDN without touching Python.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))  # so "app" can be imported

from app.main import app  # noqa: E402
