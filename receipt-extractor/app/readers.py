"""
readers.py
----------
Turns an uploaded file into something the LLM can read:
  * PDF   -> plain text (using pypdf)
  * Image -> base64 "data URL" (sent to a vision model)
"""

import base64
import io
from pathlib import PurePath

from pypdf import PdfReader
from pypdf.errors import PyPdfError

from app.config import (
    ALLOWED_EXTENSIONS,
    IMAGE_EXTENSIONS,
    MAX_FILE_SIZE_MB,
    MAX_TEXT_CHARS,
    PDF_EXTENSIONS,
)

IMAGE_MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


class ReceiptFileError(Exception):
    """Raised when a file cannot be used. The message is safe to show to the user."""


def get_extension(filename: str) -> str:
    # PurePath(...).name strips any folder part, e.g. "../../x.pdf" -> "x.pdf"
    return PurePath(filename or "").suffix.lower()


def check_file(filename: str, data: bytes) -> str:
    """Validate the file. Returns its extension, or raises ReceiptFileError."""
    extension = get_extension(filename)

    if extension not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise ReceiptFileError(f"Unsupported file type '{extension}'. Use: {allowed}")
    if not data:
        raise ReceiptFileError("The file is empty.")
    if len(data) > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise ReceiptFileError(f"File is larger than {MAX_FILE_SIZE_MB} MB.")
    return extension


def read_pdf_text(data: bytes) -> str:
    """Extract the text of every page of a PDF."""
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise ReceiptFileError("The PDF is password protected.")
        pages = [page.extract_text() or "" for page in reader.pages]
    except ReceiptFileError:
        raise
    except (PyPdfError, ValueError, OSError, KeyError, TypeError):
        raise ReceiptFileError("Could not read this PDF. It may be corrupted.")

    text = "\n".join(pages).strip()
    if not text:
        # A scanned PDF has pictures but no text. Ask for a photo instead.
        raise ReceiptFileError(
            "The PDF has no readable text (probably a scan). Upload it as a PNG/JPG photo instead."
        )
    return text[:MAX_TEXT_CHARS]


def image_to_data_url(data: bytes, extension: str) -> str:
    """Encode an image as a base64 data URL, the format vision models accept."""
    encoded = base64.b64encode(data).decode("utf-8")
    return f"data:{IMAGE_MIME_TYPES[extension]};base64,{encoded}"


def is_pdf(extension: str) -> bool:
    return extension in PDF_EXTENSIONS


def is_image(extension: str) -> bool:
    return extension in IMAGE_EXTENSIONS
