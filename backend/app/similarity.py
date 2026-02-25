"""Semantic similarity scoring using spaCy French word vectors."""

from __future__ import annotations

import logging

import numpy as np

from . import nlp_cache

logger = logging.getLogger(__name__)

_available = False


def load_model() -> None:
    """Load the shared spaCy model. Call once at startup."""
    global _available
    try:
        nlp_cache.load()
        _available = nlp_cache.get() is not None
        if _available:
            logger.info("[similarity] Model ready.")
    except Exception as exc:
        logger.warning("[similarity] Model unavailable (%s). Scores will be null.", exc)
        _available = False


def is_available() -> bool:
    return _available


def _vec(word: str):
    nlp = nlp_cache.get()
    if nlp is None:
        return None
    tok = nlp(word)[0]
    if not tok.has_vector or tok.vector_norm == 0:
        return None
    return tok.vector / tok.vector_norm


def precompute(vocab: list[str]) -> dict[str, np.ndarray]:
    """Embed all vocab words. Returns {word: unit-norm vector}."""
    if not _available or not vocab:
        return {}
    result: dict[str, np.ndarray] = {}
    for word in vocab:
        v = _vec(word)
        if v is not None:
            result[word] = v
    return result


def score_positions(
    guess_norm: str,
    vocab_embeddings: dict[str, np.ndarray],
    word_index: dict[str, list[int]],
) -> tuple[list[dict], float | None]:
    if not _available or not vocab_embeddings:
        return [], None
    try:
        guess_vec = _vec(guess_norm)
        if guess_vec is None:
            return [], None
        result: list[dict] = []
        best: float = -1.0
        for vocab_word, emb in vocab_embeddings.items():
            score = float(np.dot(emb, guess_vec))
            if score > best:
                best = score
            for pos in word_index.get(vocab_word, []):
                result.append({"pos": pos, "score": round(score, 3)})
        return result, (best if best >= 0 else None)
    except Exception as exc:
        logger.warning("[similarity] score_positions failed: %s", exc)
        return [], None
