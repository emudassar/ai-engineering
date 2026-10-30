"""
leads.py - show the call-back requests for a business.

Usage:  uv run python -m app.leads <site_id>
"""
import sys

from app.config import qdrant
from app.store import list_leads

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: uv run python -m app.leads <site_id>")

    leads = list_leads(sys.argv[1])
    if not leads:
        print("No leads yet.")
    for lead in leads:
        print(f"{lead['created_at'][:16]}  {lead['name']}  {lead['phone']}  asked: {lead['question']}")
    qdrant.close()
