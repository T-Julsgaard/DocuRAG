"""
Central configuration. Everything is driven by environment variables so the
same code runs for any knowledge base without edits — copy .env.example to
.env and fill in your values.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# --- Branding (shown in the UI) ---
APP_NAME = os.getenv("APP_NAME", "DocuRAG")
APP_TAGLINE = os.getenv("APP_TAGLINE", "knowledge base")

# --- Model used for "Ask" mode (agentic RAG) ---
ASK_MODEL = os.getenv("ASK_MODEL", "claude-haiku-4-5-20251001")

# --- Answer language ---
# Free-text hint injected into the system prompt, e.g. "English", "Danish",
# "German". The instructions file can also hard-code a language if you prefer.
ANSWER_LANGUAGE = os.getenv("ANSWER_LANGUAGE", "English")

# --- Knowledge base location ---
# Defaults to the bundled demo knowledge base one level up from /app.
_kb_path = os.getenv("KB_PATH", "").strip()
KB_ROOT = Path(_kb_path) if _kb_path else (Path(__file__).resolve().parent.parent / "knowledge_base")

# All article markdown lives here. Paths in the index are relative to KB_ROOT.
ARTICLES_PATH = KB_ROOT / "articles"

# Flat, generated index of every article (built by scripts/build_index.py).
INDEX_PATH = KB_ROOT / os.getenv("INDEX_FILE", "index.md")

# System prompt / answer-style instructions for Ask mode.
_instr = os.getenv("INSTRUCTIONS_PATH", "").strip()
INSTRUCTIONS_PATH = Path(_instr) if _instr else KB_ROOT / "instructions.md"

# --- Database ---
DB_PATH = Path(os.getenv("DB_PATH", str(Path(__file__).parent / "users.db")))

# --- Server ---
PORT = int(os.getenv("PORT", "3000"))
HOST = os.getenv("HOST", "127.0.0.1")

# --- Conversation history: how many prior user turns to send with each request ---
MAX_HISTORY = int(os.getenv("MAX_HISTORY", "5"))

# --- Default per-user daily limits (can be overridden per user in the DB) ---
ASK_DAILY_LIMIT = int(os.getenv("ASK_DAILY_LIMIT", "20"))
ASK_INPUT_TOKEN_LIMIT = int(os.getenv("ASK_INPUT_TOKEN_LIMIT", "200000"))
ASK_OUTPUT_TOKEN_LIMIT = int(os.getenv("ASK_OUTPUT_TOKEN_LIMIT", "30000"))

# Hard cap on agentic tool-use iterations per question.
MAX_ASK_ITERATIONS = int(os.getenv("MAX_ASK_ITERATIONS", "20"))
