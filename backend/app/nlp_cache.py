"""Singleton spaCy model shared by similarity.py and puzzle.py."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_nlp = None


def load(model_name: str = "fr_core_news_sm") -> None:
    """Load the spaCy model once; subsequent calls are no-ops.

    fr_core_news_sm (~12 MB) is sufficient — we only use spaCy for lemmatization.
    Word vectors come from the Gensim Word2Vec model instead.
    """
    global _nlp
    if _nlp is not None:
        return
    import spacy  # noqa: PLC0415

    logger.info("[nlp] Loading %s …", model_name)
    _nlp = spacy.load(model_name, disable=["ner", "parser"])
    logger.info("[nlp] Ready.")


def get():
    return _nlp
