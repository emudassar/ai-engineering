"""
config.py
---------
All settings live here so the other files stay clean.
Change a value here (or in the .env file) and the whole app follows.
"""

import os

from dotenv import load_dotenv

# load_dotenv() searches the current folder and then the parent folders,
# so it finds the .env file in the course root as well.
load_dotenv()

# ---------- Groq (the LLM provider) ----------
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Model used for text (PDF receipts)
TEXT_MODEL = os.getenv("TEXT_MODEL", "openai/gpt-oss-120b")

# Model used for photos (png / jpg). It must be a model that can read images.
VISION_MODEL = os.getenv("VISION_MODEL", "qwen/qwen3.8-27b")

# Reasoning models "think" before answering, so give them room, but not
# too much: Groq rejects requests that ask for more output than your limit.
MAX_OUTPUT_TOKENS = 1500

# How many times we ask the model again if its answer is not valid JSON
MAX_ATTEMPTS = 2

# ---------- Upload limits ----------
MAX_FILE_SIZE_MB = 10
MAX_FILES_PER_REQUEST = 20
MAX_TEXT_CHARS = 12000  # a receipt is short; this stops huge PDFs from costing tokens

PDF_EXTENSIONS = {".pdf"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
ALLOWED_EXTENSIONS = PDF_EXTENSIONS | IMAGE_EXTENSIONS

# ---------- Expense categories ----------
# The model must pick one of these. Anything else is flagged, not guessed.
CATEGORIES = [
    "Meals",
    "Travel",
    "Office Supplies",
    "Software",
    "Utilities",
    "Groceries",
    "Entertainment",
    "Health",
    "Other",
]

# ---------- The 6 fields we extract ----------
FIELDS = ["date", "vendor", "amount", "tax", "currency", "category"]

# Tax can be genuinely absent on a receipt, so it is the only
# field we do NOT flag when it is missing.
REQUIRED_FIELDS = ["date", "vendor", "amount", "currency", "category"]
