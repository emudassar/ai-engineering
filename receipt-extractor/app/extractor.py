"""
extractor.py
------------
The only file that talks to the LLM (Groq).

Flow: build prompt -> call model in JSON mode -> parse JSON -> validate with Pydantic.
"""

import json

from groq import APIConnectionError, APIStatusError, AuthenticationError, Groq, RateLimitError
from pydantic import ValidationError

from app.config import (
    CATEGORIES,
    GROQ_API_KEY,
    MAX_ATTEMPTS,
    MAX_OUTPUT_TOKENS,
    TEXT_MODEL,
    VISION_MODEL,
)
from app.schemas import Receipt


class ExtractionError(Exception):
    """Raised when the LLM step fails. The message is safe to show to the user."""


# ---------- Groq client ----------
# max_retries: the SDK automatically retries rate limits (429) and server errors
# with a short wait. timeout: never hang forever on one receipt.
_client = None


def get_client() -> Groq:
    global _client
    if _client is None:
        if not GROQ_API_KEY:
            raise ExtractionError("GROQ_API_KEY is missing. Add it to your .env file.")
        _client = Groq(api_key=GROQ_API_KEY, max_retries=3, timeout=60)
    return _client


# ---------- Prompt ----------
# We show the model the Pydantic JSON schema so it knows the exact shape.
SYSTEM_PROMPT = f"""
You are an expert at reading receipts and extracting expense data.

Return ONLY a valid JSON object that matches this schema:
{json.dumps(Receipt.model_json_schema()["properties"])}

Field rules:
- date: the purchase date as YYYY-MM-DD.
- vendor: the shop or company name.
- amount: the FINAL total paid (including tax), as a plain number like 12.50.
- tax: the tax amount as a plain number. Use null if no tax is shown.
- currency: a 3-letter code such as USD, EUR, GBP, PKR. Use the symbol or country to decide.
- category: exactly one of {CATEGORIES}.

Very important:
1. NEVER guess or invent a value. If a field is not clearly visible, use null.
2. If a date is ambiguous (like 03/04/2026) and you cannot be sure, use null.
3. Do not add any extra fields or any explanation. JSON only.
""".strip()


def _build_messages(receipt_text: str | None, image_url: str | None) -> list:
    """Text receipts go in as plain text, photos go in as an image."""
    if image_url:
        user_content = [
            {"type": "text", "text": "Extract the expense data from this receipt image."},
            {"type": "image_url", "image_url": {"url": image_url}},
        ]
    else:
        user_content = f"Extract the expense data from this receipt:\n\n{receipt_text}"

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


# ---------- Main function ----------
def extract_receipt(receipt_text: str | None = None, image_url: str | None = None) -> Receipt:
    """Send ONE receipt to the LLM and return a validated Receipt."""
    messages = _build_messages(receipt_text, image_url)
    model = VISION_MODEL if image_url else TEXT_MODEL
    client = get_client()
    last_problem = "unknown problem"

    for _attempt in range(MAX_ATTEMPTS):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                response_format={"type": "json_object"},
                max_completion_tokens=MAX_OUTPUT_TOKENS,
                temperature=0,  # same receipt -> same answer
            )
        except AuthenticationError:
            raise ExtractionError("Groq rejected the API key. Check GROQ_API_KEY in .env.")
        except RateLimitError:
            raise ExtractionError("Groq rate limit reached. Wait a minute and try again.")
        except APIConnectionError:
            raise ExtractionError("Could not reach Groq. Check your internet connection.")
        except APIStatusError as error:
            raise ExtractionError(f"Groq error ({error.status_code}): {error.message[:150]}")

        raw_json = response.choices[0].message.content or ""

        # The model's answer must be valid JSON AND match our Pydantic schema.
        # If not, we try again (the model sometimes cuts off or adds text).
        try:
            data = json.loads(raw_json)
            if not isinstance(data, dict):
                raise ValueError("answer is not a JSON object")
            return Receipt(**{k: v for k, v in data.items() if k in Receipt.model_fields})
        except (json.JSONDecodeError, ValueError, ValidationError) as error:
            last_problem = str(error)[:100]

    raise ExtractionError(f"The model did not return valid data ({last_problem}).")
