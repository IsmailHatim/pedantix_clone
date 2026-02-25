import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import simplemma


@dataclass
class Token:
    type: Literal["word", "sep"]
    value: str
    normalized: str | None = None  # only set for word tokens


# Matches Unicode word characters (including French accented letters), apostrophes, hyphens
_WORD_RE = re.compile(r"[\w][\w'\-]*", re.UNICODE)

# French elision: l'industrie → industrie, d'eau → eau, etc.
_ELISION_RE = re.compile(r"^(?:l|d|j|m|t|s|n|c|qu)'(.+)$", re.IGNORECASE | re.UNICODE)

# French contractions that spaCy maps to wrong lemmas (des→un, du→de, au→à, aux→à)
_CONTRACTIONS: dict[str, str] = {
    "des": "de",
    "du": "de",
    "au": "a",
    "aux": "a",
}


def normalize(word: str) -> str:
    """Lowercase and strip accents + punctuation for matching."""
    nfkd = unicodedata.normalize("NFKD", word.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def lemmatize_word(word_lower: str) -> str:
    """Return the French lemma of a lowercased (possibly accented) word.

    Uses spaCy when the model is loaded (better morphological coverage),
    falls back to simplemma otherwise.

    Pre-processing:
    - Strips French elision prefixes (l', d', …) so "l'industrie" lemmatizes
      as "industrie", not "le".
    - Explicit contraction map for "des"→"de", "du"→"de", etc. to avoid
      spaCy returning "un" for partitive "des".
    """
    from . import nlp_cache  # noqa: PLC0415 — lazy import to avoid circular dep

    # 1. Strip elision prefix
    m = _ELISION_RE.match(word_lower)
    if m:
        word_lower = m.group(1)

    # 2. Explicit contraction overrides (before calling spaCy)
    if word_lower in _CONTRACTIONS:
        return _CONTRACTIONS[word_lower]

    nlp = nlp_cache.get()
    if nlp is not None:
        tok = nlp(word_lower)[0]
        lemma = tok.lemma_
        if lemma and lemma not in ("-PRON-", ""):
            return lemma
    return simplemma.lemmatize(word_lower, lang="fr")


def tokenize(text: str) -> list[Token]:
    tokens: list[Token] = []
    pos = 0
    for m in _WORD_RE.finditer(text):
        start, end = m.start(), m.end()
        if start > pos:
            tokens.append(Token(type="sep", value=text[pos:start]))
        word = m.group()
        tokens.append(Token(type="word", value=word, normalized=normalize(word)))
        pos = end
    if pos < len(text):
        tokens.append(Token(type="sep", value=text[pos:]))
    return tokens


def build_index(tokens: list[Token]) -> dict[str, list[int]]:
    """Map normalized word → list of token indices (exact match)."""
    index: dict[str, list[int]] = {}
    for i, tok in enumerate(tokens):
        if tok.type == "word" and tok.normalized:
            index.setdefault(tok.normalized, []).append(i)
    return index


def build_lemma_index(tokens: list[Token]) -> dict[str, list[int]]:
    """Map normalize(lemma(word)) → list of token indices.

    Groups all morphological variants (conjugations, plural, etc.) under
    their shared lemma key so a single guess reveals every form.
    """
    index: dict[str, list[int]] = {}
    for i, tok in enumerate(tokens):
        if tok.type == "word" and tok.value:
            # Lemmatize the original (accented) lowercase form, then normalize
            # the lemma so both sides of the comparison are accent-free.
            lemma = lemmatize_word(tok.value.lower())
            lemma_key = normalize(lemma)
            index.setdefault(lemma_key, []).append(i)
    return index


_PUZZLE_PATH = Path(__file__).parent.parent / "puzzle.json"


def build_puzzle(
    data: dict,
) -> tuple[list[Token], dict[str, list[int]], dict[str, list[int]], str, list[Token]]:
    """Build runtime puzzle structures from a {title, intro_text} dict.

    Returns (tokens, word_index, lemma_index, title_normalized, title_tokens).
    """
    tokens = tokenize(data["intro_text"])
    word_index = build_index(tokens)
    lemma_index = build_lemma_index(tokens)
    title_normalized = normalize(data["title"])
    title_tokens = tokenize(data["title"])
    return tokens, word_index, lemma_index, title_normalized, title_tokens


def load_puzzle() -> tuple[
    list[Token], dict[str, list[int]], dict[str, list[int]], str, list[Token]
]:
    """Load from local puzzle.json (last-resort fallback)."""
    data = json.loads(_PUZZLE_PATH.read_text(encoding="utf-8"))
    return build_puzzle(data)
