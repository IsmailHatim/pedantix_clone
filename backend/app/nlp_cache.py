"""Singleton spaCy model shared by similarity.py and puzzle.py."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_nlp = None


def load(model_name: str = "fr_core_news_lg") -> None:
    """Load the spaCy model once; subsequent calls are no-ops."""
    global _nlp
    if _nlp is not None:
        return
    import spacy  # noqa: PLC0415

    logger.info("[nlp] Loading %s …", model_name)
    _nlp = spacy.load(model_name, disable=["ner"])
    logger.info("[nlp] Ready (%d vectors).", len(_nlp.vocab.vectors))


def get():
    return _nlp
