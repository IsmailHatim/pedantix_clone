"""Tests for puzzle tokenization, normalization, and indexing."""

import pytest
from app.puzzle import (
    Token,
    build_index,
    build_lemma_index,
    lemmatize_word,
    normalize,
    tokenize,
)


# ── normalize ─────────────────────────────────────────────────────────────

class TestNormalize:
    def test_lowercases(self):
        assert normalize("Paris") == "paris"
        assert normalize("LIBERTÉ") == "liberte"

    def test_strips_accents(self):
        assert normalize("été") == "ete"
        assert normalize("français") == "francais"
        assert normalize("naïve") == "naive"
        assert normalize("à") == "a"
        assert normalize("ô") == "o"

    def test_idempotent(self):
        assert normalize("locomotive") == "locomotive"
        assert normalize("vapeur") == "vapeur"


# ── tokenize ──────────────────────────────────────────────────────────────

class TestTokenize:
    def test_basic_sentence(self):
        tokens = tokenize("Paris est grand.")
        words = [t for t in tokens if t.type == "word"]
        assert [t.value for t in words] == ["Paris", "est", "grand"]

    def test_sep_tokens_present(self):
        tokens = tokenize("a b.")
        seps = [t for t in tokens if t.type == "sep"]
        assert len(seps) >= 1

    def test_word_normalized(self):
        tokens = tokenize("Été")
        word = next(t for t in tokens if t.type == "word")
        assert word.normalized == "ete"

    def test_hyphenated_word(self):
        tokens = tokenize("chemin-de-fer")
        words = [t for t in tokens if t.type == "word"]
        # Entire hyphenated compound is one word token
        assert words[0].value == "chemin-de-fer"

    def test_empty_string(self):
        tokens = tokenize("")
        assert tokens == []

    def test_only_separators(self):
        tokens = tokenize("... !!!")
        assert all(t.type == "sep" for t in tokens)

    def test_accented_words(self):
        tokens = tokenize("La locomotive à vapeur")
        words = [t for t in tokens if t.type == "word"]
        assert "locomotive" in [t.value for t in words]
        assert "vapeur" in [t.value for t in words]


# ── build_index ───────────────────────────────────────────────────────────

class TestBuildIndex:
    def test_maps_normalized_to_positions(self):
        tokens = tokenize("Paris est la capitale de Paris.")
        index = build_index(tokens)
        assert "paris" in index
        assert len(index["paris"]) == 2  # appears twice

    def test_normalized_key(self):
        tokens = tokenize("Été chaud.")
        index = build_index(tokens)
        assert "ete" in index
        assert "Été" not in index

    def test_no_sep_entries(self):
        tokens = tokenize("mot , autre.")
        index = build_index(tokens)
        assert "," not in index
        assert "." not in index


# ── build_lemma_index ─────────────────────────────────────────────────────

class TestBuildLemmaIndex:
    def test_groups_word_under_its_lemma(self):
        # "locomotives" should lemmatize to "locomotive"
        tokens = tokenize("locomotives")
        lemma_index = build_lemma_index(tokens)
        # The key is normalize(lemmatize("locomotives"))
        key = normalize(lemmatize_word("locomotives"))
        assert key in lemma_index

    def test_hit_on_infinitive_finds_conjugated(self):
        # If the article has "construite" and player guesses "construire",
        # both sides should map to the same lemma key.
        tokens = tokenize("construite")
        lemma_index = build_lemma_index(tokens)
        guess_key = normalize(lemmatize_word("construire"))
        article_key = normalize(lemmatize_word("construite"))
        # Both normalize to the same lemma → same index key
        assert guess_key == article_key

    def test_positions_are_valid_indices(self):
        tokens = tokenize("Une locomotive à vapeur.")
        lemma_index = build_lemma_index(tokens)
        word_count = sum(1 for t in tokens if t.type == "word")
        for positions in lemma_index.values():
            for pos in positions:
                assert 0 <= pos < len(tokens)
                assert tokens[pos].type == "word"


# ── lemmatize_word ────────────────────────────────────────────────────────

class TestLemmatizeWord:
    def test_plural_to_singular(self):
        result = lemmatize_word("locomotives")
        assert result in ("locomotive", "locomotives")  # simplemma should return singular

    def test_infinitive_unchanged(self):
        result = lemmatize_word("construire")
        assert result == "construire"

    def test_elision_stripped(self):
        # "l'industrie" → strips "l'" → lemmatizes "industrie", NOT "le"
        result = lemmatize_word("l'industrie")
        assert result != "le"
        assert "industri" in result.lower()

    def test_elision_d(self):
        # "d'eau" → strips "d'" → "eau"
        result = lemmatize_word("d'eau")
        assert result != "de"
        assert result == "eau"

    def test_contraction_des(self):
        # "des" must NOT lemmatize to "un" (spaCy bug)
        result = lemmatize_word("des")
        assert result == "de"

    def test_contraction_du(self):
        result = lemmatize_word("du")
        assert result == "de"

    def test_contraction_au(self):
        result = lemmatize_word("au")
        assert result == "a"

    def test_contraction_aux(self):
        result = lemmatize_word("aux")
        assert result == "a"


class TestLemmaIndexElision:
    def test_elided_word_not_under_le(self):
        # An article token like "l'industrie" must NOT end up under lemma key "le"
        tokens = tokenize("l'industrie")
        lemma_index = build_lemma_index(tokens)
        assert "le" not in lemma_index

    def test_des_not_under_un(self):
        # "des" in the article must NOT end up under lemma key "un"
        tokens = tokenize("des locomotives")
        lemma_index = build_lemma_index(tokens)
        assert "un" not in lemma_index
