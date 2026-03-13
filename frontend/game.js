'use strict';

// ── State ──────────────────────────────────────────────────────────────────
let gameId      = null;
let state       = null;   // latest game state from API
let wizardMode  = false;  // true while the human is selecting a wizard target
let actionInProgress = false; // prevents re-entrant auto-pass

// ── API ────────────────────────────────────────────────────────────────────
// Flask serves both frontend and API from the same origin.
const API = '';

async function apiFetch(path, options = {}) {
  const res = await fetch(API + path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

// ── Setup ──────────────────────────────────────────────────────────────────
document.getElementById('start-btn').addEventListener('click', startGame);

async function startGame() {
  const width      = parseInt(document.getElementById('cfg-width').value)  || 12;
  const height     = parseInt(document.getElementById('cfg-height').value) || 10;
  const seedRaw    = document.getElementById('cfg-seed').value.trim();
  const difficulty = document.getElementById('cfg-difficulty').value;
  const errEl      = document.getElementById('setup-error');
  errEl.classList.add('hidden');

  const body = { width, height, difficulty };
  if (seedRaw) body.seed = parseInt(seedRaw);

  try {
    const data = await apiFetch('/game/new', {
      method: 'POST',
      body: JSON.stringify(body),
    });
    gameId     = data.game_id;
    state      = data;
    wizardMode = false;

    document.getElementById('setup-screen').classList.add('hidden');
    document.getElementById('game-screen').classList.remove('hidden');
    renderAll();
  } catch (e) {
    errEl.textContent = e.message;
    errEl.classList.remove('hidden');
  }
}

// ── Rendering ─────────────────────────────────────────────────────────────

const TYPE_LABEL = {
  forest: 'F', plains: 'P', tower: 'T', cave: 'C',
  wizard: 'W', barbarian: 'B', mountain: '⛰', domain: 'D',
};

function computeTileSize() {
  const area = document.getElementById('board-area');
  const hud  = document.getElementById('hud');
  const areaW = area.clientWidth  - 4;
  const areaH = area.clientHeight - hud.offsetHeight - 4;
  const byW   = Math.floor(areaW / state.width);
  const byH   = Math.floor(areaH / state.height);
  return Math.max(Math.min(byW, byH), 24);
}

function renderAll() {
  const tileSize = computeTileSize();
  document.documentElement.style.setProperty('--tile-size', `${tileSize}px`);

  renderBoard(tileSize);
  renderHUD();
  // Kick off auto-pass asynchronously so the board renders first,
  // but only when no other action is already in progress.
  if (!actionInProgress) setTimeout(() => autoPassIfNeeded(), 0);
}

function renderBoard(tileSize) {
  if (!state || !state.board) return;

  const boardEl = document.getElementById('board');
  boardEl.style.gridTemplateColumns = `repeat(${state.width}, ${tileSize}px)`;
  boardEl.style.gridTemplateRows    = `repeat(${state.height}, ${tileSize}px)`;

  // Only show valid moves on the human's turn; hide them while AI is playing
  const validSet = (state.turn === 'human')
    ? new Set((state.valid_moves || []).map(([r, c]) => `${r},${c}`))
    : new Set();
  const wizSet = wizardMode ? buildWizardTargets() : new Set();

  // Build into a fragment first — if anything throws, the existing board is untouched
  const frag = document.createDocumentFragment();
  try {
    for (let r = 0; r < state.height; r++) {
      for (let c = 0; c < state.width; c++) {
        frag.appendChild(buildTile(r, c, validSet, wizSet));
      }
    }
  } catch (err) {
    console.error('renderBoard error at tile', err);
    return; // leave current board visible rather than going black
  }

  boardEl.innerHTML = '';
  boardEl.appendChild(frag);
}

function buildTile(r, c, validSet, wizSet) {
  const tile = (state.board[r] || [])[c];
  if (!tile) {
    const blank = document.createElement('div');
    blank.className = 'tile t-fog';
    return blank;
  }
  const key = `${r},${c}`;
  const isValid   = !wizardMode && validSet.has(key);
  const isWizVis  =  wizardMode && wizSet.has(key) &&  tile.visible;  // gold highlight
  const isWizFog  =  wizardMode && wizSet.has(key) && !tile.visible;  // clickable fog

  const div = document.createElement('div');
  div.className = 'tile';
  div.dataset.r = r;
  div.dataset.c = c;

  // Base colour class
  if (!tile.visible) {
    div.classList.add('t-fog');
  } else if (tile.owner === 'human') {
    div.classList.add('o-human');
  } else if (tile.owner === 'ai') {
    div.classList.add('o-ai');
  } else {
    div.classList.add(`t-${tile.type}`);
  }

  // Asset image — renders over the placeholder colour; ignored silently on 404
  div.style.backgroundImage    = `url('${getAssetPath(tile)}')`;
  div.style.backgroundSize     = '100% 100%';
  div.style.backgroundRepeat   = 'no-repeat';

  // Tile type label — shown on claimed and visible unclaimed tiles
  if (tile.visible && tile.type !== 'mountain') {
    const lbl = document.createElement('span');
    lbl.className   = 'tile-lbl';
    lbl.textContent = TYPE_LABEL[tile.type] || '';
    div.appendChild(lbl);
  }

  // Interaction classes
  if (isValid) {
    div.classList.add('valid');
    div.addEventListener('click', () => handleTileClick(r, c, false));
  } else if (isWizVis) {
    div.classList.add('wiz-target');
    div.addEventListener('click', () => handleTileClick(r, c, true));
  } else if (isWizFog) {
    div.classList.add('wiz-fog');
    div.addEventListener('click', () => handleTileClick(r, c, true));
  }

  return div;
}

function renderHUD() {
  // Turn
  const turnEl = document.getElementById('turn-label');
  if (state.turn === 'human') {
    turnEl.textContent = wizardMode ? '✨ Choose a teleport destination' : '⚔️  Your Turn';
    turnEl.style.color = 'var(--c-human)';
  } else {
    turnEl.textContent = '🤖  AI Turn';
    turnEl.style.color = 'var(--c-ai)';
  }

  // Scores
  document.getElementById('score-human').textContent = state.scores.human;
  document.getElementById('score-ai').textContent    = state.scores.ai;

  // Remaining claimable tiles
  let total = 0;
  state.board.forEach(row => row.forEach(t => { if (t.type !== 'mountain') total++; }));
  const remaining = total - state.scores.human - state.scores.ai;
  document.getElementById('remaining').textContent = remaining;

  // Seed
  document.getElementById('seed-display').textContent = state.seed;

  // Wizard
  updateWizardHUD();
}

function updateWizardHUD() {
  const hudEl   = document.getElementById('wizard-hud');
  const lblEl   = document.getElementById('wizard-label');
  const btnEl   = document.getElementById('wizard-btn');

  const held = state.wizard_held_by;
  const avail = state.wizard_available;

  if (!held) {
    hudEl.classList.add('hidden');
    return;
  }

  hudEl.classList.remove('hidden');

  const wizardUsed = state.wizard_used || {};

  if (held === 'human') {
    if (wizardUsed.human) {
      lblEl.textContent = '✨ Wizard used';
      btnEl.classList.add('hidden');
    } else if (avail) {
      lblEl.textContent = '✨ Wizard ready';
      btnEl.classList.remove('hidden');
      btnEl.textContent = wizardMode ? 'Cancel' : 'Use Wizard';
    } else {
      // Human holds it but it's AI's turn
      lblEl.textContent = '✨ Wizard ready';
      btnEl.classList.add('hidden');
    }
  } else {
    // AI holds wizard
    lblEl.textContent = wizardUsed.ai ? '🤖 AI used wizard' : '🤖 AI holds wizard';
    btnEl.classList.add('hidden');
  }
}

// ── Wizard mode toggle ─────────────────────────────────────────────────────
document.getElementById('wizard-btn').addEventListener('click', () => {
  if (state.status !== 'in_progress' || state.turn !== 'human') return;
  wizardMode = !wizardMode;
  renderAll();
});

function buildWizardTargets() {
  const s = new Set();
  state.board.forEach((row, r) => {
    row.forEach((tile, c) => {
      if (tile.owner === null && tile.type !== 'mountain' && tile.type !== 'barbarian') {
        s.add(`${r},${c}`);
      }
    });
  });
  return s;
}

// ── Auto-pass when human has no moves ─────────────────────────────────────
function humanHasMoves() {
  const hasNormal = (state.valid_moves || []).length > 0;
  const hasWizard = state.wizard_available;
  return hasNormal || hasWizard;
}

async function autoPassIfNeeded() {
  if (state.status !== 'in_progress') return;
  if (state.turn !== 'human')         return;
  if (wizardMode)                     return; // human is selecting a wizard target
  if (humanHasMoves())                return;

  actionInProgress = true;
  toast('No valid moves — passing turn…', 2000);
  await sleep(800);

  let data;
  try {
    data = await apiFetch(`/game/${gameId}/pass`, { method: 'POST' });
  } catch (e) {
    console.error('Pass error:', e.message);
    actionInProgress = false;
    return;
  }

  state = data;
  renderAll();

  if (state.status !== 'in_progress') {
    actionInProgress = false;
    showEndModal();
    return;
  }

  if (state.turn === 'ai') {
    await runAI();
  }

  actionInProgress = false;
}

// ── Move handling ──────────────────────────────────────────────────────────
async function handleTileClick(r, c, isWizard) {
  if (state.status !== 'in_progress') return;
  if (state.turn !== 'human')         return;

  await submitMove(r, c, isWizard);
}

async function submitMove(r, c, wizard = false) {
  wizardMode = false;
  actionInProgress = true;

  let data;
  try {
    data = await apiFetch(`/game/${gameId}/move`, {
      method: 'POST',
      body: JSON.stringify({ row: r, col: c, wizard }),
    });
  } catch (e) {
    console.error('Move error:', e.message);
    toast(`Move failed: ${e.message}`, 3000);
    actionInProgress = false;
    renderAll();
    return;
  }

  state = data;
  renderAll();

  await handleBarbarians(data.events || []);

  if (state.status !== 'in_progress') {
    actionInProgress = false;
    showEndModal();
    return;
  }

  if (state.turn === 'ai') {
    await runAI();
  }

  actionInProgress = false;
}

// ── AI move ────────────────────────────────────────────────────────────────
// Runs AI turns in a loop: if the human still has no moves after the AI
// plays, silently passes for them and lets the AI go again.
// Times out after 10 s and falls back to a forced quick move (depth 1).
async function runAI() {
  actionInProgress = true;

  while (state.status === 'in_progress' && state.turn === 'ai') {
    if (!gameId) break; // game was abandoned (New Game clicked)

    setThinking(true);

    let data;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10_000);

    try {
      [data] = await Promise.all([
        fetch(API + `/game/${gameId}/ai-move`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          signal: controller.signal,
        }).then(async r => {
          const d = await r.json();
          if (!r.ok) throw new Error(d.error || `HTTP ${r.status}`);
          return d;
        }),
        sleep(600),
      ]);
      clearTimeout(timeoutId);
    } catch (e) {
      clearTimeout(timeoutId);
      setThinking(false);
      if (e.name === 'AbortError') {
        // 10 s timeout — request a depth-1 forced move.
        // The server may have already completed the original request, so if
        // force=1 is rejected (wrong turn), fall back to fetching current state.
        try {
          data = await apiFetch(`/game/${gameId}/ai-move?force=1`, { method: 'POST' });
        } catch (e2) {
          console.error('AI forced move failed, recovering state:', e2.message);
          try {
            data = await apiFetch(`/game/${gameId}`);
          } catch (e3) {
            break;
          }
        }
      } else {
        console.error('AI move error:', e.message);
        try {
          data = await apiFetch(`/game/${gameId}`);
        } catch (e2) {
          break;
        }
      }
    }

    setThinking(false);

    if (!gameId) break; // abandoned while waiting

    state = data;
    renderAll();

    await handleBarbarians(data.events || []);

    if (state.status !== 'in_progress') {
      actionInProgress = false;
      showEndModal();
      return;
    }

    // If the human still has no moves, silently pass their turn and loop
    if (state.turn === 'human' && !humanHasMoves()) {
      let passData;
      try {
        passData = await apiFetch(`/game/${gameId}/pass`, { method: 'POST' });
      } catch (e) {
        console.error('Pass error:', e.message);
        break;
      }

      state = passData;
      renderAll();

      if (state.status !== 'in_progress') {
        actionInProgress = false;
        showEndModal();
        return;
      }
      // state.turn is now 'ai' — loop condition re-evaluated
    }
  }

  // Safety net: ensure spinner is off and board reflects latest state
  setThinking(false);
  if (state) renderAll();
  actionInProgress = false;
}

// ── Barbarian flash ────────────────────────────────────────────────────────
async function handleBarbarians(events) {
  const barbs = events.filter(e => e.type === 'barbarian_triggered');
  if (!barbs.length) return;

  const count = barbs.length;
  toast(`⚔️ Barbarian${count > 1 ? 's charge' : ' charges'}!`, 1400);

  barbs.forEach(ev => flashPath(ev.position[0], ev.position[1], ev.direction));

  // Wait for CSS animation to finish before moving on
  await sleep(3100);
}

function flashPath(br, bc, direction) {
  const tiles = chargePath(br, bc, direction);
  tiles.forEach(([r, c]) => {
    const el = document.querySelector(`.tile[data-r="${r}"][data-c="${c}"]`);
    if (!el) return;
    // Remove and re-add to restart animation if multiple barbs hit same tile
    el.classList.remove('barb-flash');
    void el.offsetWidth; // force reflow
    el.classList.add('barb-flash');
    el.addEventListener('animationend', () => el.classList.remove('barb-flash'), { once: true });
  });
}

function chargePath(r, c, direction) {
  const tiles = [];
  // Sweep from the barbarian's tile outward toward the edge
  if (direction === 'left')  { for (let nc = c;        nc >= 0;           nc--) tiles.push([r, nc]); }
  if (direction === 'right') { for (let nc = c;        nc < state.width;  nc++) tiles.push([r, nc]); }
  if (direction === 'up')    { for (let nr = r;        nr >= 0;           nr--) tiles.push([nr, c]); }
  if (direction === 'down')  { for (let nr = r;        nr < state.height; nr++) tiles.push([nr, c]); }
  return tiles;
}

// ── UI helpers ─────────────────────────────────────────────────────────────
function setThinking(on) {
  document.getElementById('turn-spinner').classList.toggle('hidden', !on);
  if (on) {
    const lbl = document.getElementById('turn-label');
    lbl.textContent   = '🤖 AI is thinking…';
    lbl.style.color   = 'var(--c-ai)';
  }
}

let toastTimer = null;
function toast(msg, duration = 2000) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.classList.remove('hidden');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.add('hidden'), duration);
}

function showEndModal() {
  const modal   = document.getElementById('end-modal');
  const titleEl = document.getElementById('end-title');
  const scoreEl = document.getElementById('end-score-line');

  if      (state.status === 'human_wins') titleEl.textContent = '🏆 You Win!';
  else if (state.status === 'ai_wins')    titleEl.textContent = '🤖 AI Wins!';
  else                                    titleEl.textContent = "🤝 It's a Tie!";

  scoreEl.textContent =
    `Final Score — You: ${state.scores.human}  ·  AI: ${state.scores.ai}`;

  modal.classList.remove('hidden');
}

document.getElementById('play-again-btn').addEventListener('click', () => {
  document.getElementById('end-modal').classList.add('hidden');
  document.getElementById('game-screen').classList.add('hidden');
  document.getElementById('setup-screen').classList.remove('hidden');
  gameId = state = null;
  wizardMode = false;
  actionInProgress = false;
});

document.getElementById('new-game-btn').addEventListener('click', () => {
  gameId = null;
  state = null;
  wizardMode = false;
  actionInProgress = false;
  document.getElementById('end-modal').classList.add('hidden');
  document.getElementById('game-screen').classList.add('hidden');
  document.getElementById('setup-screen').classList.remove('hidden');
});

// ── Asset mapping ──────────────────────────────────────────────────────────
// Returns the expected PNG path for a tile.  If the file doesn't exist the
// browser silently ignores the background-image and the CSS colour shows through.
function getAssetPath(tile) {
  const { type, owner, inert, visible } = tile;

  // Fogged tile
  if (!visible && !owner) return 'assets/fog.png';

  switch (type) {
    case 'mountain':
      return 'assets/mountain.png';

    case 'barbarian':
      return 'assets/barbarian.png';

    case 'wizard':
      return 'assets/wizard.png';

    case 'cave':
      return `assets/cave_neutral.png`;
      if (owner) {
        const side = owner === 'human' ? 'player' : 'ai';
        return inert ? `assets/cave_inert_${side}.png` : `assets/cave_${side}.png`;
      }
      

    case 'domain':
      // Domain tiles are always owned; no neutral variant in the spec
      return `assets/domain.png`;
      return `assets/domain_${owner === 'human' ? 'player' : 'ai'}.png`;

    default:
      // forest, plains, tower
      return `assets/${type}_neutral.png`
      if (owner === 'human') return `assets/${type}_player.png`;
      if (owner === 'ai')    return `assets/${type}_ai.png`;
      return `assets/${type}_neutral.png`;
  }
}

// ── Utility ────────────────────────────────────────────────────────────────
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
