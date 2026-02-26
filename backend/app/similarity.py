"""Semantic similarity scoring.

Primary backend: Gensim KeyedVectors (frWiki Word2Vec by Fauconnier).
Fallback: spaCy fr_core_news_lg word vectors (already loaded for lemmatization).

Set WORD2VEC_MODEL_PATH to the path of the .bin model file to activate the
Gensim backend.  When the file is absent the spaCy fallback is used automatically.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from . import config, nlp_cache

logger = logging.getLogger(__name__)

# Gensim KeyedVectors instance (None when not loaded)
_kv = None
_available = False


def load_model() -> None:
    """Load Gensim model if path is configured, otherwise fall back to spaCy."""
    global _kv, _available

    model_path = Path(config.WORD2VEC_MODEL_PATH).resolve()
    logger.info("[similarity] Looking for Word2Vec model at: %s", model_path)
    if model_path.exists():
        try:
            from gensim.models import KeyedVectors  # noqa: PLC0415
            logger.info("[similarity] Loading Word2Vec model from %s …", model_path)
            _kv = KeyedVectors.load_word2vec_format(str(model_path), binary=True)
            _available = True
            logger.info(
                "[similarity] Word2Vec ready — %d words in vocabulary.", len(_kv)
            )
            return
        except Exception as exc:
            logger.warning(
                "[similarity] Could not load Word2Vec model (%s). Falling back to spaCy.", exc
            )

    # spaCy fallback (already loaded by nlp_cache for lemmatization)
    try:
        nlp_cache.load()
        _available = nlp_cache.get() is not None
        if _available:
            logger.info("[similarity] Using spaCy word vectors as fallback.")
        else:
            logger.warning("[similarity] No similarity model available.")
    except Exception as exc:
        logger.warning("[similarity] spaCy fallback unavailable (%s).", exc)
        _available = False


def is_available() -> bool:
    return _available


# ---------------------------------------------------------------------------
# Dictionary check
# ---------------------------------------------------------------------------

def is_in_vocab(word: str) -> bool:
    """Return True if *word* is in the loaded model's vocabulary.

    When the Gensim model is loaded this gives exact Pedantix-style validation
    (frWiki vocabulary, cutoff 200).  When the model is not loaded, all words
    are allowed (no restriction).
    """
    if _kv is None:
        return True  # Gensim model not loaded — no restriction
    return word.lower() in _kv


# ---------------------------------------------------------------------------
# Embedding helpers
# ---------------------------------------------------------------------------

def _vec_gensim(word: str) -> np.ndarray | None:
    if _kv is None or word not in _kv:
        return None
    v = _kv[word].astype(np.float32)
    norm = np.linalg.norm(v)
    return v / norm if norm > 0 else None


def _vec_spacy(word: str) -> np.ndarray | None:
    nlp = nlp_cache.get()
    if nlp is None:
        return None
    tok = nlp(word)[0]
    if not tok.has_vector or tok.vector_norm == 0:
        return None
    return tok.vector / tok.vector_norm


def _vec(word: str) -> np.ndarray | None:
    return _vec_gensim(word) if _kv is not None else _vec_spacy(word)


# ---------------------------------------------------------------------------
# Public API (unchanged contract)
# ---------------------------------------------------------------------------

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
