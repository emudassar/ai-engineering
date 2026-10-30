"""
config.py - settings and shared clients.

Everything that talks to the outside world (Groq, Qdrant, the embedding
model) is created ONCE here, and the other modules import it from here.
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from fastembed import TextEmbedding
from groq import Groq
from qdrant_client import QdrantClient

PROJECT_DIR = Path(__file__).parent.parent

# Only this project's .env, never one from a parent folder. On Vercel there is no
# .env file: the same variables are set in the project's Environment Variables.
load_dotenv(PROJECT_DIR / ".env")

# ---------------- Settings ----------------
LLM_MODEL = "openai/gpt-oss-120b"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"  # gives 384-number vectors
VECTOR_SIZE = 384
COLLECTION = "local_biz_bot"  # one Qdrant collection holds every business

MAX_PAGES = 30     # stop crawling a website after this many pages
CHUNK_WORDS = 150  # words per text chunk
TOP_K = 4          # chunks retrieved for each question

# Where the backend is reachable. Used to print the <script> snippet.
BACKEND_URL = os.getenv("BACKEND_URL") or os.getenv("RENDER_EXTERNAL_URL") or "http://localhost:8000"

# ---------------- Clients ----------------
groq_client = Groq()  # reads GROQ_API_KEY from the environment
embedder = TextEmbedding(EMBED_MODEL)

# Qdrant Cloud when QDRANT_URL is set, otherwise a local folder (no account needed).
if os.getenv("QDRANT_URL"):
    qdrant = QdrantClient(url=os.environ["QDRANT_URL"], api_key=os.getenv("QDRANT_API_KEY"))
else:
    qdrant = QdrantClient(path=str(PROJECT_DIR / "qdrant_data"))
