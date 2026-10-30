"""
pipeline.py
-----------
Connects all the steps for ONE file:

    check file -> read it -> ask the LLM -> validate -> ReceiptRow

process_file() NEVER raises. If anything goes wrong, it returns a row with
status "error" so one bad file can not break a batch of 20.
"""

from app.extractor import ExtractionError, extract_receipt
from app.readers import (
    ReceiptFileError,
    check_file,
    image_to_data_url,
    is_image,
    read_pdf_text,
)
from app.schemas import ReceiptRow
from app.validation import find_problems


def process_file(filename: str, data: bytes) -> ReceiptRow:
    safe_name = filename or "unnamed"

    try:
        extension = check_file(safe_name, data)

        if is_image(extension):
            receipt = extract_receipt(image_url=image_to_data_url(data, extension))
        else:
            receipt = extract_receipt(receipt_text=read_pdf_text(data))

    except (ReceiptFileError, ExtractionError) as error:
        return ReceiptRow(file=safe_name, status="error", notes=str(error))
    except Exception:  # last safety net: an unexpected bug must not kill the batch
        return ReceiptRow(file=safe_name, status="error", notes="Unexpected error while reading this file.")

    problems = find_problems(receipt)
    status = "needs_review" if problems else "ok"
    return ReceiptRow(**receipt.model_dump(), file=safe_name, status=status, notes="; ".join(problems))
