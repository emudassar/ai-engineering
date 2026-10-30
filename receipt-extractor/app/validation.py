"""
validation.py
-------------
Decides if a row is trustworthy.

Rule of this project: a missing field is FLAGGED, never guessed.
"""

from app.config import REQUIRED_FIELDS
from app.schemas import Receipt


def find_problems(receipt: Receipt) -> list[str]:
    """Return a list of human-readable problems. Empty list = row is fine."""
    problems = []

    # 1. Missing required fields
    missing = [name for name in REQUIRED_FIELDS if getattr(receipt, name) is None]
    if missing:
        problems.append("Missing: " + ", ".join(missing))

    # 2. Numbers that do not make sense together
    if receipt.amount is not None and receipt.amount == 0:
        problems.append("Amount is 0")
    if receipt.amount is not None and receipt.tax is not None and receipt.tax > receipt.amount:
        problems.append("Tax is bigger than the total")

    return problems
