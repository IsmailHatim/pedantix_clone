import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import numpy as np
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from . import config, dictionary, similarity, wiki
from .models import (
    GuessRequest,
    GuessResponse,
    TitleGuessRequest,
    TitleGuessResponse,
)
from .puzzle import Token, build_puzzle, lemmatize_word, load_puzzle, normalize

logger = logging.getLogger(__name__)

_CACHE_PATH = Path(__file__).parent.parent / "puzzle_cache.json"
_FALLBACK_PATH = Path(__file__).parent.parent / "puzzle.json"

# ---------------------------------------------------------------------------
# Puzzle state (loaded once at startup)
# ---------------------------------------------------------------------------
_tokens: list[Token] = []
_title_tokens: list[Token] = []
_word_index: dict[str, list[int]] = {}
_lemma_index: dict[str, list[int]] = {}
_title_lemma_index: dict[str, list[int]] = {}
_vocab_embeddings: dict[str, np.ndarray] = {}
_title_normalized: str = ""
_title: str = ""
_PUZZLE_ID: str = "unknown"


async def _load_puzzle_data() -> dict:
    """Try Wikipedia fetch → cached JSON → hardcoded fallback."""
    # 1. Try Wikipedia
    try:
        data = await wiki.fetch_intro(
            config.WIKI_PAGE_TITLE, max_paragraphs=config.MAX_PARAGRAPHS
        )
        _CACHE_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info("[puzzle] Fetched from Wikipedia: %s", data["title"])
        return data
    except Exception as exc:
        logger.warning("[puzzle] Wikipedia fetch failed (%s). Trying cache.", exc)

    # 2. Try puzzle_cache.json
    if _CACHE_PATH.exists():
        try:
            data = json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
            logger.info("[puzzle] Loaded from cache: %s", data.get("title"))
            return data
        except Exception as exc:
            logger.warning("[puzzle] Cache read failed (%s). Using fallback.", exc)

    # 3. Hardcoded puzzle.json
    data = json.loads(_FALLBACK_PATH.read_text(encoding="utf-8"))
    logger.info("[puzzle] Loaded from hardcoded fallback: %s", data.get("title"))
    return data


@asynccontextmanager
async def lifespan(app: FastAPI):
    global \
        _tokens, \
        _title_tokens, \
        _word_index, \
        _lemma_index, \
        _title_lemma_index, \
        _vocab_embeddings, \
        _title_normalized, \
        _title, \
        _PUZZLE_ID

    # Load similarity model (blocking, runs once)
    similarity.load_model()

    data = await _load_puzzle_data()
    _tokens, _word_index, _lemma_index, _title_normalized, _title_tokens = build_puzzle(
        data
    )
    from .puzzle import build_lemma_index as _build_lemma_index

    _title_lemma_index = _build_lemma_index(_title_tokens)
    _title = data["title"]
    _PUZZLE_ID = f"wiki-{normalize(_title)}"

    # Precompute embeddings for all unique vocabulary words
    _vocab_embeddings = similarity.precompute(list(_word_index.keys()))
    if _vocab_embeddings:
        logger.info(
            "[similarity] Precomputed embeddings for %d vocab words.",
            len(_vocab_embeddings),
        )

    yield


class NgrokSkipWarningMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["ngrok-skip-browser-warning"] = "1"
        return response


app = FastAPI(lifespan=lifespan)

app.add_middleware(NgrokSkipWarningMiddleware)

_STATIC_DIR = Path(__file__).parent.parent / "static"


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------


@app.get("/api/puzzle")
def get_puzzle():
    """Return masked token streams for both title and body."""
    # Body tokens
    body_stream = []
    total_words = 0
    for tok in _tokens:
        if tok.type == "word":
            body_stream.append({"t": "word", "len": len(tok.value)})
            total_words += 1
        else:
            body_stream.append({"t": "sep", "v": tok.value})

    # Title tokens
    title_stream = []
    for tok in _title_tokens:
        if tok.type == "word":
            title_stream.append({"t": "word", "len": len(tok.value)})
        else:
            title_stream.append({"t": "sep", "v": tok.value})

    return {
        "puzzle_id": _PUZZLE_ID,
        "language": "fr",
        "title_tokens": title_stream,
        "tokens": body_stream,
        "meta": {"total_words": total_words},
        "admin_mode": config.ADMIN_MODE,
    }


@app.post("/api/guess", response_model=GuessResponse)
def post_guess(body: GuessRequest):
    guess = body.guess.strip()
    if len(guess) < config.MIN_GUESS_LENGTH:
        return GuessResponse(status="invalid", positions=[])

    if not dictionary.is_known(guess):
        return GuessResponse(status="unknown", positions=[])

    # Lemma lookup: covers exact match + all morphological variants (conjugations, plurals…)
    lemma = normalize(lemmatize_word(guess.lower()))

    # Check title tokens independently so title words are always revealed on a match
    title_positions = _title_lemma_index.get(lemma, [])
    title_revealed_texts = (
        {str(pos): _title_tokens[pos].value for pos in title_positions}
        if title_positions
        else None
    )

    # Always compute similarity — used for labels on misses AND on hits for unrevealed words
    norm = normalize(guess)
    pos_scores, best_score = similarity.score_positions(
        norm, _vocab_embeddings, _word_index
    )

    positions = _lemma_index.get(lemma, [])
    if positions:
        revealed_set = {str(p) for p in positions}
        revealed_texts = {str(pos): _tokens[pos].value for pos in positions}
        # Keep similarity labels only for positions not being revealed right now
        hit_scores = [
            p
            for p in pos_scores
            if p["score"] >= config.MIN_LABEL_SCORE
            and str(p["pos"]) not in revealed_set
        ]
        return GuessResponse(
            status="hit",
            positions=positions,
            revealed_texts=revealed_texts,
            title_revealed_texts=title_revealed_texts,
            word_scores=hit_scores if hit_scores else None,
        )

    pos_scores = [p for p in pos_scores if p["score"] >= config.MIN_LABEL_SCORE]
    return GuessResponse(
        status="miss",
        positions=[],
        similarity=best_score,
        word_scores=pos_scores,
        title_revealed_texts=title_revealed_texts,
    )


@app.post("/api/guess_title", response_model=TitleGuessResponse)
def post_guess_title(body: TitleGuessRequest):
    norm = normalize(body.title_guess.strip())
    solved = norm == _title_normalized
    return TitleGuessResponse(solved=solved, title=_title if solved else None)


# Mount static files last so API routes take priority
app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="static")
