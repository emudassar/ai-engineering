"""Entry point for Vercel, which looks for an `app` object in main.py.

Locally you can keep using:  uv run uvicorn app.main:app --reload
"""

from app.main import app  # noqa: F401
