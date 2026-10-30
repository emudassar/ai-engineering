"""
schemas.py
----------
Pydantic models. They describe the shape of the data we want and
clean up whatever the LLM gives us.
"""

import re
from datetime import date as date_type

from pydantic import BaseModel, field_validator

from app.config import CATEGORIES


def _to_number(value):
    """Turn '$1,234.50' or '12,50' or 12 into a float. Return None if it is not a number."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = re.sub(r"[^\d,.\-]", "", str(value))  # drop currency symbols and spaces
    if not text:
        return None
    # "12,50" (comma as decimal) -> "12.50", but "1,234.50" keeps working
    if "," in text and "." not in text and re.search(r",\d{2}$", text):
        text = text.replace(",", ".")
    text = text.replace(",", "")
    try:
        return float(text)
    except ValueError:
        return None


class Receipt(BaseModel):
    """What the LLM must return for one receipt. Every field can be None (= missing)."""

    date: str | None = None  # always YYYY-MM-DD
    vendor: str | None = None
    amount: float | None = None  # the final total paid
    tax: float | None = None
    currency: str | None = None  # 3-letter code, e.g. USD
    category: str | None = None  # must be one of CATEGORIES

    @field_validator("date", mode="before")
    @classmethod
    def check_date(cls, value):
        # Keep the date only if it is a real calendar date in YYYY-MM-DD format.
        if value is None:
            return None
        try:
            return date_type.fromisoformat(str(value).strip()).isoformat()
        except ValueError:
            return None

    @field_validator("vendor", mode="before")
    @classmethod
    def check_vendor(cls, value):
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @field_validator("amount", "tax", mode="before")
    @classmethod
    def check_numbers(cls, value):
        number = _to_number(value)
        # A negative total or tax makes no sense on a normal receipt
        if number is not None and number < 0:
            return None
        return number

    @field_validator("currency", mode="before")
    @classmethod
    def check_currency(cls, value):
        if value is None:
            return None
        text = str(value).strip().upper()
        return text if re.fullmatch(r"[A-Z]{3}", text) else None

    @field_validator("category", mode="before")
    @classmethod
    def check_category(cls, value):
        if value is None:
            return None
        # Case-insensitive match against our allowed list
        for allowed in CATEGORIES:
            if str(value).strip().lower() == allowed.lower():
                return allowed
        return None


class ReceiptRow(Receipt):
    """One row of the final result = the receipt fields + info about the file."""

    file: str
    status: str  # "ok", "needs_review" or "error"
    notes: str = ""  # explains why a row needs review or failed
