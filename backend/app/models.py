from typing import Literal

from pydantic import BaseModel


class GuessRequest(BaseModel):
    guess: str


class GuessResponse(BaseModel):
    status: Literal["hit", "miss", "invalid"]
    positions: list[int]
    revealed_texts: dict[str, str] | None = None        # body pos (str) → actual token text
    title_revealed_texts: dict[str, str] | None = None  # title pos (str) → actual token text
    similarity: float | None = None      # best score across all positions (for history badge)
    word_scores: list[dict] | None = None  # [{pos, score}] for every word position


class TitleGuessRequest(BaseModel):
    title_guess: str


class TitleGuessResponse(BaseModel):
    solved: bool
    title: str | None = None
