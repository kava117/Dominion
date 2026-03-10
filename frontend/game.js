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
  const wrap = document.getElementById('board-wrap');
  const maxW = wrap.clientWidth  - 4;
  const maxH = wrap.clientHeight - 4;
  const byW  = Math.floor(maxW / state.width);
  const byH  = Math.floor(maxH / state.height);
  return Math.max(Math.min(byW, byH, 48), 16);
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
  const boardEl = document.getElementById('board');
  boardEl.style.gridTemplateColumns = `repeat(${state.width},  ${tileSize}px)`;
  boardEl.style.gridTemplateRows    = `repeat(${state.height}, ${tileSize}px)`;

  const validSet = new Set((state.valid_moves || []).map(([r, c]) => `${r},${c}`));
  const wizSet   = wizardMode ? buildWizardTargets() : new Set();

  boardEl.innerHTML = '';

  for (let r = 0; r < state.height; r++) {
    for (let c = 0; c < state.width; c++) {
      boardEl.appendChild(buildTile(r, c, validSet, wizSet));
    }
  }
}

function buildTile(r, c, validSet, wizSet) {
  const tile  = state.board[r][c];
  const key   = `${r},${c}`;
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

  if (held === 'human') {
    if (avail) {
      lblEl.textContent = '✨ Wizard ready';
      btnEl.classList.remove('hidden');
      btnEl.textContent = wizardMode ? 'Cancel' : 'Use Wizard';
    } else {
      lblEl.textContent = '✨ Wizard used';
      btnEl.classList.add('hidden');
    }
  } else {
    // AI holds wizard
    lblEl.textContent = avail ? '🤖 AI holds wizard' : '🤖 AI used wizard';
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
      if (tile.owner === null && tile.type !== 'mountain') {
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
    actionInProgress = false;
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
async function runAI() {
  actionInProgress = true;
  setThinking(true);

  let data;
  try {
    // Run fetch and a minimum display timer concurrently
    [data] = await Promise.all([
      apiFetch(`/game/${gameId}/ai-move`, { method: 'POST' }),
      sleep(600),
    ]);
  } catch (e) {
    setThinking(false);
    console.error('AI move error:', e.message);
    return;
  }

  setThinking(false);

  state = data;
  renderAll();

  await handleBarbarians(data.events || []);

  if (state.status !== 'in_progress') {
    actionInProgress = false;
    showEndModal();
    return;
  }

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
  if (direction === 'left')  { for (let nc = 0;        nc <= c;           nc++) tiles.push([r, nc]); }
  if (direction === 'right') { for (let nc = c;        nc < state.width;  nc++) tiles.push([r, nc]); }
  if (direction === 'up')    { for (let nr = 0;        nr <= r;           nr++) tiles.push([nr, c]); }
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

    case 'wizard': {
      // Show wizard_used.png after the ability has been consumed
      const used = owner && state.wizard_used[owner];
      return used ? 'assets/wizard_used.png' : 'assets/wizard.png';
    }

    case 'cave':
      if (owner) {
        const side = owner === 'human' ? 'player' : 'ai';
        return inert ? `assets/cave_inert_${side}.png` : `assets/cave_${side}.png`;
      }
      return 'assets/cave_neutral.png';

    case 'domain':
      // Domain tiles are always owned; no neutral variant in the spec
      return `assets/domain_${owner === 'human' ? 'player' : 'ai'}.png`;

    default:
      // forest, plains, tower
      if (owner === 'human') return `assets/${type}_player.png`;
      if (owner === 'ai')    return `assets/${type}_ai.png`;
      return `assets/${type}_neutral.png`;
  }
}

// ── Utility ────────────────────────────────────────────────────────────────
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
