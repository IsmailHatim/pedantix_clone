# Pedantix Clone

A French Wikipedia word-reveal guessing game. The introduction of a hidden Wikipedia article is displayed as masked tokens. Guess words to reveal them; guess the article title to win.

## Stack

- **Backend:** FastAPI + spaCy `fr_core_news_lg` (lemmatization & word vectors)
- **Frontend:** Vanilla JS, no framework
- **Data:** Wikipedia MediaWiki API → `puzzle_cache.json` → `puzzle.json` fallback

## Run

```bash
cd backend
pip install -r requirements.txt
python -m spacy download fr_core_news_lg

# Download the Word2Vec model (dictionary + similarity, ~500 MB)
# https://fauconnier.github.io/#data  →  frWiki_no_phrase_no_postag_1000_skip_cut200.bin
# Place the .bin file in backend/ or set WORD2VEC_MODEL_PATH to its location.

uvicorn app.main:app --reload
```

Open [http://localhost:8000](http://localhost:8000).

## Config (env vars)

| Variable | Default | Description |
|---|---|---|
| `WIKI_PAGE_TITLE` | `Locomotive à vapeur` | Wikipedia article to use |
| `WORD2VEC_MODEL_PATH` | `frWiki_no_phrase_no_postag_1000_skip_cut200.bin` | Path to Gensim `.bin` model |
| `MAX_PARAGRAPHS` | `2` | Number of intro paragraphs to include |
| `MIN_LABEL_SCORE` | `0.40` | Minimum similarity score to show a label |
| `ADMIN_MODE` | `true` | Show the reset button |

## Tests

```bash
cd backend
pytest
```
