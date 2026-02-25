"""Centralised runtime configuration loaded from environment variables."""

import os

# Suppress HuggingFace / tokenizer noise
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("HF_HUB_VERBOSITY", "error")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")

WIKI_PAGE_TITLE: str = os.getenv("WIKI_PAGE_TITLE", "Locomotive à vapeur")

MAX_PARAGRAPHS: int = int(os.getenv("MAX_PARAGRAPHS", "2"))
MIN_GUESS_LENGTH: int = int(os.getenv("MIN_GUESS_LENGTH", "1"))
MIN_LABEL_SCORE: float = float(os.getenv("MIN_LABEL_SCORE", "0.40"))
ADMIN_MODE: bool = os.getenv("ADMIN_MODE", "true").lower() in ("1", "true", "yes")
