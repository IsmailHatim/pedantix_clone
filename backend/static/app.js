/* =========================================================
   Pedantix Clone — client
   State stored in localStorage under key "pedantix_state"
   ========================================================= */

const STATE_KEY = "pedantix_state";

let puzzleTokens = [];
let titleTokens  = [];
let puzzleId     = null;

let state = {
  puzzle_id:       null,
  revealed:        {},   // pos (str) → actual token text (lemma hit)
  title_revealed:  {},   // title pos (str) → actual token text
  best_match:      {},   // pos (str) → {word, score} (best miss so far)
  last_miss_word:  null, // most recently submitted miss word (shown in heat colors)
  history:         [],   // [{word, status, score}]
  solved:          false,
  solved_title:    null,
};

// ── Helpers ──────────────────────────────────────────────────────────────

function loadState() {
  try { const r = localStorage.getItem(STATE_KEY); if (r) return JSON.parse(r); }
  catch (_) {}
  return null;
}
function saveState() { localStorage.setItem(STATE_KEY, JSON.stringify(state)); }

function extractWords(text) {
  // \p{L} matches any Unicode letter (including accented French: à, é, ô …)
  return [...text.matchAll(/\p{L}[\p{L}'\-]*/gu)].map(m => m[0]);
}

// ── Score → CSS class ────────────────────────────────────────────────────

function tokenScoreClass(score) {
  if (score >= 0.82) return "score-hot";
  if (score >= 0.70) return "score-warm";
  if (score >= 0.58) return "score-mild";
  if (score >= 0.45) return "score-cold";
  return "score-frozen";
}

function badgeScoreClass(score) {
  if (score >= 0.78) return "hot";
  if (score >= 0.62) return "warm";
  return "cold";
}

// ── Title rendering ──────────────────────────────────────────────────────

function buildTitleDisplay() {
  const el = document.getElementById("title-display");
  el.innerHTML = "";
  titleTokens.forEach((tok, pos) => {
    if (tok.t === "sep") {
      el.appendChild(document.createTextNode(tok.v));
    } else {
      const span = document.createElement("span");
      span.dataset.titlePos = pos;
      const posStr = String(pos);
      if (state.title_revealed[posStr]) {
        span.className = "token revealed";
        span.textContent = state.title_revealed[posStr];
      } else {
        span.className = "token masked";
        span.textContent = "█".repeat(tok.len);
      }
      el.appendChild(span);
    }
  });
}

function revealTitlePositions(revealedTexts) {
  Object.entries(revealedTexts).forEach(([posStr, text]) => {
    state.title_revealed[posStr] = text;
    const span = document.querySelector(`[data-title-pos="${posStr}"]`);
    if (span) {
      span.className = "token revealed";
      span.textContent = text;
    }
  });
}

function revealTitleDisplay(canonicalTitle) {
  const words = extractWords(canonicalTitle);
  let wi = 0;
  document.querySelectorAll("[data-title-pos]").forEach(span => {
    if (wi < words.length) {
      span.classList.replace("masked", "revealed");
      span.textContent = words[wi++];
    }
  });
}

// ── Body rendering ───────────────────────────────────────────────────────

function buildDisplay() {
  const el = document.getElementById("text-display");
  el.innerHTML = "";

  puzzleTokens.forEach((tok, pos) => {
    if (tok.t === "sep") {
      el.appendChild(document.createTextNode(tok.v));
      return;
    }
    const span = document.createElement("span");
    span.dataset.pos = pos;

    const posStr = String(pos);
    if (state.revealed[posStr]) {
      span.className = "token revealed";
      span.textContent = state.revealed[posStr];
    } else if (state.best_match[posStr]) {
      const { word, score } = state.best_match[posStr];
      const isLatest = state.last_miss_word && word === state.last_miss_word;
      span.className = `token labeled ${tokenScoreClass(score)}${isLatest ? " latest" : ""}`;
      span.textContent = word;
    } else {
      span.className = "token masked";
      span.textContent = "█".repeat(tok.len);
    }
    el.appendChild(span);
  });
}

// Mark a set of positions as exactly revealed (hit)
// revealedTexts: { "posStr": "actualTokenText", ... }
function revealPositions(revealedTexts) {
  Object.entries(revealedTexts).forEach(([posStr, displayWord]) => {
    state.revealed[posStr] = displayWord;
    delete state.best_match[posStr];   // remove any lingering label
    const span = document.querySelector(`[data-pos="${posStr}"]`);
    if (span) {
      span.className = "token revealed";
      span.textContent = displayWord;
    }
  });
}

// Update best_match state for every position where this guess scores better.
// Does NOT update the DOM — caller is responsible for calling buildDisplay().
function updateBestMatch(posScores, displayWord) {
  posScores.forEach(({ pos, score }) => {
    const posStr = String(pos);
    if (state.revealed[posStr]) return;    // already revealed — skip
    const cur = state.best_match[posStr];
    if (!cur || score > cur.score) {
      state.best_match[posStr] = { word: displayWord, score };
    }
  });
}

// ── History ───────────────────────────────────────────────────────────────

function makeHistoryItem(num, word, status, score) {
  const li = document.createElement("li");
  li.className = status;

  const numSpan = document.createElement("span");
  numSpan.className = "hist-num";
  numSpan.textContent = num;
  li.appendChild(numSpan);

  const wordSpan = document.createElement("span");
  wordSpan.className = "hist-word";
  wordSpan.textContent = word;
  li.appendChild(wordSpan);

  if (status === "miss" && score != null) {
    const badge = document.createElement("span");
    badge.className = `score-badge ${badgeScoreClass(score)}`;
    badge.textContent = score.toFixed(2);
    li.appendChild(badge);
  }

  return li;
}

function addHistory(word, status, score = null) {
  const num = state.history.length + 1;
  state.history.push({ word, status, score });
  document.getElementById("history").prepend(makeHistoryItem(num, word, status, score));
}

function renderHistory() {
  const ul = document.getElementById("history");
  ul.innerHTML = "";
  [...state.history].reverse().forEach(({ word, status, score }, i) => {
    ul.appendChild(makeHistoryItem(state.history.length - i, word, status, score ?? null));
  });
}

// ── Solved ────────────────────────────────────────────────────────────────

function isTitleComplete() {
  return titleTokens.every((tok, pos) => {
    if (tok.t !== "word") return true;
    return !!state.title_revealed[String(pos)];
  });
}

function reconstructTitle() {
  return titleTokens.map((tok, pos) => {
    if (tok.t === "sep") return tok.v;
    return state.title_revealed[String(pos)] || "";
  }).join("");
}

let _unknownTimer = null;
function showUnknownMsg(word) {
  const el = document.getElementById("unknown-msg");
  el.textContent = `« ${word} » — Je ne connais pas ce mot.`;
  el.classList.remove("hidden");
  if (_unknownTimer) clearTimeout(_unknownTimer);
  _unknownTimer = setTimeout(() => el.classList.add("hidden"), 3000);
}

function showSolved() {
  document.getElementById("solved-banner").classList.remove("hidden");
  document.getElementById("guess-form").querySelector("button").disabled = true;
  if (state.solved_title) revealTitleDisplay(state.solved_title);
}

// ── API ───────────────────────────────────────────────────────────────────

async function fetchPuzzle() {
  const r = await fetch("/api/puzzle");
  if (!r.ok) throw new Error("Failed to fetch puzzle");
  return r.json();
}

async function postGuess(guess) {
  const r = await fetch("/api/guess", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ guess }),
  });
  return r.json();
}

async function postTitleGuess(guess) {
  const r = await fetch("/api/guess_title", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title_guess: guess }),
  });
  return r.json();
}

// ── Event handler (unified input) ─────────────────────────────────────────

document.getElementById("guess-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (state.solved) return;

  const input = document.getElementById("guess-input");
  const word = input.value.trim();
  input.value = "";
  if (!word) return;

  const [wordData, titleData] = await Promise.all([postGuess(word), postTitleGuess(word)]);

  // Unknown word — show message, no history entry
  if (wordData.status === "unknown") {
    showUnknownMsg(word);
    return;
  }

  // Reveal title words that match this guess (applies to hits, misses, and full-title guess)
  if (wordData.title_revealed_texts && Object.keys(wordData.title_revealed_texts).length) {
    revealTitlePositions(wordData.title_revealed_texts);
  }

  if (wordData.status === "hit") {
    revealPositions(wordData.revealed_texts || {});
    // Also update similarity labels for still-unrevealed positions
    if (wordData.word_scores && wordData.word_scores.length) {
      updateBestMatch(wordData.word_scores, word);
      buildDisplay();
    }
  } else if (wordData.status === "miss") {
    // Update state, then rebuild display so latest miss shows in heat colors
    // and all previous labels become gray
    state.last_miss_word = word;
    updateBestMatch(wordData.word_scores || [], word);
    buildDisplay();
  }

  // Win condition 1: user typed the full title
  // Win condition 2: all individual title words are now revealed
  const wonByFullTitle = titleData.solved;
  const wonByReveal    = !state.solved && isTitleComplete();

  if (wonByFullTitle || wonByReveal) {
    state.solved = true;
    state.solved_title = titleData.title ?? reconstructTitle();
    addHistory(word, "win");
    saveState();
    showSolved();
  } else if (wordData.status === "hit") {
    addHistory(word, "hit");
    saveState();
  } else if (wordData.status === "invalid") {
    addHistory(word, "invalid");
    saveState();
  } else {
    addHistory(word, "miss", wordData.similarity ?? null);
    saveState();
  }
});

// ── Init ──────────────────────────────────────────────────────────────────

async function init() {
  const puzzle = await fetchPuzzle();
  puzzleId     = puzzle.puzzle_id;
  puzzleTokens = puzzle.tokens;
  titleTokens  = puzzle.title_tokens || [];

  const saved = loadState();
  if (saved && saved.puzzle_id === puzzleId) {
    state = saved;
    state.best_match     = state.best_match     || {};   // backward compat
    state.last_miss_word = state.last_miss_word  ?? null; // backward compat
    state.title_revealed = state.title_revealed  || {};   // backward compat
  } else {
    state = {
      puzzle_id: puzzleId, revealed: {}, title_revealed: {}, best_match: {},
      last_miss_word: null, history: [], solved: false, solved_title: null,
    };
    saveState();
  }

  if (!puzzle.admin_mode) {
    document.getElementById("reset-btn").classList.add("hidden");
  }

  buildTitleDisplay();
  buildDisplay();
  renderHistory();
  if (state.solved) showSolved();
}

document.getElementById("reset-btn").addEventListener("click", () => {
  if (confirm("Recommencer depuis zéro ?")) {
    localStorage.removeItem(STATE_KEY);
    location.reload();
  }
});

init().catch(err => console.error("Init failed:", err));
