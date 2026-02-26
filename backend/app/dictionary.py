"""French dictionary validation.

Uses the loaded Word2Vec model vocabulary (frWiki by Fauconnier) when available —
the same vocabulary used for semantic similarity scoring.
Falls back to permitting all words when no model is loaded.
"""

from . import similarity


def is_known(word: str) -> bool:
    """Return True if *word* is a known French word."""
    return similarity.is_in_vocab(word)
