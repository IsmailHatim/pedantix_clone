# Pedantix Clone

A French Wikipedia word-reveal guessing game. The introduction of a hidden Wikipedia article is displayed as masked tokens. Guess words to reveal them; guess the article title to win.

## Stack

- **Backend:** FastAPI + spaCy `fr_core_news_sm` (lemmatization) + Gensim Word2Vec (similarity & dictionary)
- **Frontend:** Vanilla JS, no framework
- **Data:** Wikipedia MediaWiki API → `puzzle_cache.json` → `puzzle.json` fallback

## Run

```bash
cd backend
pip install -r requirements.txt
python -m spacy download fr_core_news_sm

# Download the Word2Vec model (dictionary validation + similarity scoring, ~500 MB)
# https://fauconnier.github.io/#data  →  frWiki_no_lem_no_postag_no_phrase_1000_skip_cut200.bin
# Place the .bin file in backend/ or set WORD2VEC_MODEL_PATH to its location.

uvicorn app.main:app --reload
```

Open [http://localhost:8000](http://localhost:8000).

## How it works

- Every word token in the article is masked. Guessing a word reveals all its occurrences (lemma-aware: guessing "être" reveals "est", "était", etc.).
- Every guess also runs semantic similarity against all remaining hidden words — close matches appear as gray labels (darker = further, lighter = closer).
- Only words from the frWiki vocabulary are accepted; unknown words are rejected with "Je ne connais pas ce mot."
- The game is won when all title words are individually revealed.
- State is fully client-side (localStorage).

## Config (env vars)

| Variable | Default | Description |
|---|---|---|
| `WIKI_PAGE_TITLE` | `Locomotive à vapeur` | Wikipedia article to use |
| `WORD2VEC_MODEL_PATH` | `frWiki_no_lem_no_postag_no_phrase_1000_skip_cut200.bin` | Path to Gensim `.bin` model |
| `MAX_PARAGRAPHS` | `2` | Number of intro paragraphs to include |
| `MIN_LABEL_SCORE` | `0.30` | Minimum similarity score to show a label |
| `ADMIN_MODE` | `true` | Show the reset button |

## Tests

```bash
cd backend
pytest
```

## Acknowledgements

- **[Pédantix](https://pedantix.certitudes.org)** by [Enigmatix](https://pedantix.certitudes.org) — the original French daily Wikipedia guessing game this project is inspired by.

- **[French Word Embeddings](https://fauconnier.github.io/#data)** by Jean-Philippe Fauconnier — pre-trained Word2Vec models for French used for similarity scoring and dictionary validation. Licensed under [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/).

  > Fauconnier, Jean-Philippe (2015). *French Word Embeddings*. http://fauconnier.github.io

- **[Wikipédia](https://fr.wikipedia.org)** — article content fetched via the MediaWiki API.
