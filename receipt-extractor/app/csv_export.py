"""
csv_export.py
-------------
Turns a list of ReceiptRow into CSV text.
"""

import csv
import io

from app.config import FIELDS
from app.schemas import ReceiptRow

COLUMNS = ["file", *FIELDS, "status", "notes"]


def safe_cell(value) -> str:
    """Empty for None. Also stops "CSV injection": a cell starting with = + - @
    would run as a formula when opened in Excel, so we prefix it with a quote."""
    if value is None:
        return ""
    text = str(value)
    if text and text[0] in "=+-@\t\r":
        return "'" + text
    return text


def rows_to_csv(rows: list[ReceiptRow]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(COLUMNS)
    for row in rows:
        data = row.model_dump()
        writer.writerow([safe_cell(data[column]) for column in COLUMNS])
    return buffer.getvalue()
