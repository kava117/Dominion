# Domain Expansion — Implementation Plan

**Stack**: Python/Flask backend + Vanilla JS/HTML/CSS frontend. Flask serves both the API and static files. No npm, no build tools.

Each stage must pass all its tests before proceeding to the next.

---

## Stage 1 — Project Scaffolding

**Goal**: Flask app runs, serves a bare HTML page, and passes a health-check test.

### Backend
1. Create `backend/requirements.txt`: `flask`, `flask-cors`, `pytest`
2. Create `backend/game/__init__.py`, `backend/game/ai/__init__.py` (empty)
3. Create `backend/main.py`:
   - Flask app with `GET /ping` → `{"status": "ok"}`
   - `GET /` serves `frontend/index.html`
   - `Flask static_folder` points to `frontend/`
4. Create `backend/pytest.ini` pointing test discovery at `backend/tests/`
5. Create `backend/tests/__init__.py` and `backend/tests/conftest.py`

### Frontend
1. Create `frontend/index.html`: bare HTML shell with `<div id="app">` and script imports
2. Create `frontend/style.css`: empty
3. Create `frontend/js/api.js`, `board.js`, `hud.js`, `app.js`: empty stubs
4. Create `frontend/js/assetMap.js`: empty export object

### Tests — Stage 1
- `tests/test_api.py`: `GET /ping` returns 200 and `{"status": "ok"}`
- `tests/test_api.py`: `GET /` returns 200 and HTML content

---

## Stage 2 — Board Generation

**Goal**: Backend generates a valid, seeded board with all tile types placed correctly.

### Implementation
1. **`backend/seed.py`**: wrap `random.Random(seed)` as a seedable RNG helper
2. **`backend/game/board.py`**:
   - `Tile` dataclass: `type`, `owner` (`None`/`"human"`/`"ai"`), `visible` (bool), `connected` (bool, for caves)
   - `TILE_TYPES`: `forest`, `plains`, `tower`, `cave`, `mountain`, `wizard`, `barbarian`, `domain`
   - `generate_board(width, height, seed, domain_tiles_per_player=2) -> list[list[Tile]]`:
     1. Fill all tiles as `forest`
     2. Place mountains: randomly pick 10–20% of tiles
     3. Place special tiles scaled to board size:
        - Wizard: exactly 1
        - Barbarians: 1–3 groups (1 tile each)
        - Caves: even number ≥ 2, scaled with board size
        - Towers: scaled with board size
        - Plains: scaled with board size
     4. Remaining non-special, non-mountain tiles stay `forest`
     5. Place starting Domain tiles: for each player, place `domain_tiles_per_player` tiles on non-mountain, non-special tiles, not adjacent to each other or the opposing player's domains; set `owner`

### Tests — Stage 2
- `tests/test_board.py`:
  - Same seed → identical board
  - Mountain count is 10–20% of total tiles
  - Exactly 1 Wizard tile
  - Cave count is even and ≥ 2
  - Domain tiles have correct owner, not on mountains/specials, not adjacent to each other
  - Board dimensions match requested width/height
  - All tile types are valid `TILE_TYPES`

---

## Stage 3 — Game State Model

**Goal**: `GameState` encapsulates all mutable data and serializes to the API response shape.

### Implementation
1. **`backend/game/state.py`**:
   - `GameState` class:
     - `game_id: str`
     - `board: list[list[Tile]]`
     - `width, height: int`
     - `seed: int`
     - `difficulty: str`
     - `turn: str` (`"human"` or `"ai"`)
     - `status: str` (`"in_progress"`, `"human_wins"`, `"ai_wins"`, `"draw"`)
     - `scores: dict` (`{"human": int, "ai": int}`)
     - `wizard_held_by: str | None`
     - `wizard_used: bool`
     - `valid_moves_human: dict[tuple, str]` — `{(row,col): source_type}`
     - `valid_moves_ai: dict[tuple, str]`
     - `pending_cave_human: tuple | None`
     - `pending_cave_ai: tuple | None`
     - `awaiting_plains: bool` — True when human claimed Plains and second move is pending
   - `to_dict(perspective: str) -> dict`: serialize to API JSON shape; tiles not yet visible show `"type": "unknown"` from that player's perspective
   - `new_game(config: dict) -> GameState`: calls `generate_board`, initializes all fields, computes initial valid moves

2. **`backend/database.py`**: in-memory `GAMES: dict[str, GameState]` with `save(state)` and `load(game_id)`

### Tests — Stage 3
- `tests/conftest.py`: fixture that creates a default `GameState`
- `tests/test_api.py`:
  - `new_game()` returns `GameState` with correct fields
  - `to_dict("human")` matches the JSON shape from spec section 12
  - Fogged tiles show `"type": "unknown"` from human perspective

---

## Stage 4 — Valid Moves Engine

**Goal**: `rules.py` correctly computes valid moves for any game state.

### Implementation
1. **`backend/game/rules.py`**:
   - `compute_valid_moves(board, owned_tiles, all_claimed, pending_cave, wizard_available) -> dict[tuple, str]`
     - Returns `{(row, col): source_type}` where `source_type` is the granting tile type
     - Per tile type of each owned tile:
       - `forest` / `domain`: cardinal neighbors that are unclaimed, non-mountain → source `"forest"`
       - `plains`: unclaimed, non-mountain tiles at Manhattan distance ≥ 2 → source `"plains"`
       - `tower`: unclaimed, non-mountain tiles at **exactly** Manhattan distance 3 → source `"tower"`
       - `cave` (when `pending_cave` is set): all other unclaimed cave tiles → source `"cave"`
     - Source priority: if a tile is reachable by a permanent type (forest/plains/tower) AND by cave, permanent wins
   - `cardinal_neighbors(row, col, width, height) -> list[tuple]`
   - `manhattan(a, b) -> int`

2. Wire into `GameState`: call `compute_valid_moves` for both players after every state change

### Tests — Stage 4
- `tests/test_moves.py`:
  - Domain tile: all 4 cardinal neighbors (non-mountain, unclaimed) in valid moves
  - Mountains never in valid moves
  - Already-claimed tiles never in valid moves
  - Plains: distance-1 tiles NOT added; distance ≥ 2 added
  - Tower: only exact distance-3 tiles added
  - Cave pending: unclaimed caves added with source `"cave"`; non-caves not added unless from other source
  - Priority: cave tile also reachable by forest → source is `"forest"`, not `"cave"`

---

## Stage 5 — Core API Endpoints

**Goal**: All five API routes work and correctly mutate state.

### Implementation
1. **`backend/main.py`** — implement all routes:
   - `POST /game/new` — parse config, call `new_game()`, save, return `to_dict("human")`
   - `GET /game/<id>` — load, return `to_dict("human")`
   - `GET /game/<id>/valid-moves` — return `{"valid_moves": [[r,c],...]}`
   - `POST /game/<id>/move` — body: `{"row": r, "col": c}`:
     1. Validate human's turn and `(r,c)` in `valid_moves_human`
     2. Claim the tile; stub special effects (no-op for now)
     3. Recompute valid moves for both players
     4. Stub win check
     5. Switch turn to `"ai"` (unless `awaiting_plains`)
     6. Save and return updated state
   - `POST /game/<id>/ai-move` — stub: pick a random valid AI move, apply it, switch turn to `"human"`, return state
2. Enable CORS for local development

### Tests — Stage 5
- `tests/test_api.py`:
  - `POST /game/new` → 200, valid game state JSON
  - `GET /game/<id>` → 200, same state
  - `GET /game/<id>/valid-moves` → list of `[row, col]` pairs
  - `POST /game/<id>/move` valid move → 200, tile claimed, turn = `"ai"`
  - `POST /game/<id>/move` invalid coords → 400
  - `POST /game/<id>/move` on AI's turn → 400
  - `POST /game/<id>/ai-move` → 200, AI tile claimed, turn = `"human"`

---

## Stage 6 — Win Conditions

**Goal**: Game correctly detects all terminal states.

### Implementation
1. **`backend/game/win.py`**:
   - `check_win(state: GameState) -> str | None`: returns `"human_wins"`, `"ai_wins"`, `"draw"`, or `None`
   - **Standard end**: no unclaimed non-mountain tiles remain → compare scores
   - **Dominant end**: one player's score > (total claimable / 2) AND opponent's valid moves pool is empty → that player wins

2. Call `check_win` after every move; set `state.status` if terminal

### Tests — Stage 6
- `tests/test_win_conditions.py`:
  - All claimable tiles taken, human leads → `"human_wins"`
  - All claimable tiles taken, equal → `"draw"`
  - Human > 50% and AI has no moves → `"human_wins"` (dominant)
  - Game in progress → `None`
  - Mountains excluded from all counts
  - API: move on a finished game → 400

---

## Stage 7 — Special Tile Effects

**Goal**: All six special tile types apply correct effects when claimed.

### Implementation
Add `apply_tile_effect(state, player, row, col)` in `backend/game/effects.py`, called during move processing.

#### 7a — Plains
- Mark tiles within Manhattan distance ≤ 2 as `visible = True`
- Do NOT switch turns after claiming; set `state.awaiting_plains = True`
- Next move from same player is the Plains bonus move; after it, clear `awaiting_plains` and switch turns

#### 7b — Tower
- Mark all tiles within Manhattan distance ≤ 3 as `visible = True`
- Add tiles at exactly distance 3 (non-mountain, unclaimed) to the player's valid moves

#### 7c — Cave
- Set `pending_cave_<player> = (row, col)`
- Next move: if target is a Cave and `source_type == "cave"`, mark both caves `connected = True`, clear `pending_cave`; else just clear `pending_cave`
- Connected caves never offered as cave destinations

#### 7d — Wizard
- Set `state.wizard_held_by = player`
- API: if move body includes `"wizard_activate": true`, target may be any unclaimed non-mountain tile; after claiming, set `wizard_used = True`, clear `wizard_held_by`

#### 7e — Barbarians
- On any `visible = True` transition for a barbarian tile, trigger immediately:
  1. Pick direction: longer axis (row vs column)
  2. Uncllaim every tile in that full row or column (`owner = None`); mountains stay mountains
  3. Replace barbarian tile with `type = "forest"`, `owner = None`
  4. Recompute valid moves for both players

#### 7f — Domain
- Identical to Forest for move generation (cardinal adjacency)

### Tests — Stage 7
- `tests/test_specials.py`:
  - **Plains**: visible tiles correct; `awaiting_plains` set; second move switches turns
  - **Tower**: distance ≤ 3 tiles visible; only distance-3 in valid moves
  - **Cave**: `pending_cave` set; next cave claim connects both; non-cave next move clears without connecting; connected caves excluded from destinations; forest-reachable cave not consumed
  - **Wizard**: `wizard_held_by` set; activate claims any unclaimed tile; `wizard_used` set
  - **Barbarians**: row/column unclaimed; barbarian becomes forest; mountains unaffected; freed tiles reclaimed after recompute
- `tests/test_e2e.py`: play a full game via the API verifying state at each step

---

## Stage 8 — AI Engine

**Goal**: AI selects moves via minimax with alpha-beta pruning.

### Implementation
1. **`backend/game/heuristic.py`** — `evaluate(state) -> float` (from AI perspective):
   - `tile_delta`: AI score − human score
   - `moves_delta`: AI valid moves count − human valid moves count
   - `special_bonus`: +weight for Wizard/Tower/Cave in AI valid moves pool
   - `barbarian_penalty`: penalty if barbarian visible and threatens AI tiles
   - `cave_bonus`: bonus per connected Cave pair owned by AI
   - Return weighted sum

2. **`backend/game/ai/minimax.py`** — `minimax(state, depth, alpha, beta, maximizing) -> (score, move)`:
   - Depth 0 or terminal: return `(evaluate(state), None)`
   - Move ordering: Wizard > Tower > Cave > Plains > Forest/Domain; then by valid-moves expansion
   - **Plains**: expand as compound node — enumerate all (first, second) move pairs in one minimax node
   - **Wizard**: if `wizard_held_by == "ai"`, include wizard-activate as candidate
   - Depth by difficulty: Easy=2, Medium=4, Hard=6

3. Replace random stub in `ai-move` route with `minimax` call

### Tests — Stage 8
- `tests/test_ai.py`:
  - AI always returns a valid move
  - AI never picks an already-claimed tile
  - AI picks a higher-value special tile when one is obviously available (depth ≥ 2)
  - Plains: AI evaluates both moves in a single node
  - Wizard: AI considers wizard activation in candidate list

---

## Stage 9 — Frontend

**Goal**: Browser renders the full game: board, fog, valid move highlights, HUD, and end modal. Human interaction flows correctly through the API.

### Implementation
1. **`frontend/js/api.js`**: `fetch()` wrappers:
   - `newGame(config)`, `getGame(id)`, `getValidMoves(id)`, `submitMove(id, row, col, wizardActivate)`, `triggerAiMove(id)`

2. **`frontend/js/assetMap.js`**: map tile keys (e.g. `"forest_player"`) to placeholder CSS colors per spec section 10.2

3. **`frontend/js/board.js`**:
   - `renderBoard(boardData, validMoves, onTileClick, interactive)`: builds CSS grid of tile `<div>` elements
   - Each div: background color from `assetMap`; semi-transparent white overlay if valid move; fog color if `!visible`
   - Tile size: 32×32px; scales down for large boards

4. **`frontend/js/hud.js`**: `updateHUD(state)`:
   - Turn indicator, human/AI scores, remaining claimable tiles, wizard held-by, seed
   - "AI is thinking…" indicator when `turn === "ai"`
   - "Use Wizard" button when `wizard_held_by === "human"`

5. **`frontend/index.html`**:
   - `<div id="setup-screen">`: width, height, seed, difficulty inputs + Start button
   - `<div id="game-screen">`: board container + HUD panel (hidden until game starts)
   - `<div id="end-modal">`: winner text, scores, Play Again button (hidden until game ends)

6. **`frontend/js/app.js`** — game loop:
   - On Start: call `newGame()`, hide setup, show game, render board
   - On tile click: call `submitMove()` → update board and HUD → if `turn === "ai"`, call `triggerAiMove()` → update again
   - Plains two-step: if `awaiting_plains`, keep board interactive for one more click
   - On `status !== "in_progress"`: show end modal
   - Wizard mode: clicking "Use Wizard" enters target-selection mode; any unclaimed tile is clickable; submit with `wizardActivate=true`

### Tests — Stage 9
Manual browser smoke tests (no test framework needed):
- Setup screen renders; Start button creates a game and shows the board
- Board tile count matches width × height
- Valid move tiles have the highlight overlay
- Clicking a non-valid tile does nothing
- Clicking a valid tile updates the board and shows AI turn indicator
- AI turn completes and board updates
- End modal appears with correct winner text
- Play Again resets to setup screen

---

## Stage 10 — Polish & Integration

**Goal**: Fully playable end-to-end with edge cases handled.

### Implementation
1. **`start.sh`**: `cd backend && flask run` (single command; Flask serves everything)
2. Error handling: API errors surface as a visible alert banner in the UI
3. AI thinking delay: disable board clicks during AI turn; re-enable on response
4. Responsive board: CSS `calc` so tiles scale to fit viewport; compact 16×16 mode when board > 16 wide
5. Barbarian visual: briefly flash freed tiles before re-render
6. Cave UX: after claiming a cave, valid move highlights update to show cave destinations distinctly
7. "Copy Seed" button in HUD copies seed to clipboard

### Final Tests — Stage 10
- `tests/test_e2e.py` (backend):
  - Full game via API: new game → alternate human/AI moves until `status != "in_progress"`
  - Final scores sum to total claimable tiles (accounting for any barbarian resets)
  - Same seed → same board → same move sequence → same outcome
- Browser: full play-through from setup to end modal without console errors

---

## Run Commands

```bash
# Install backend deps
pip install -r backend/requirements.txt

# Run backend (also serves frontend)
cd backend && flask run

# Run backend tests
cd backend && pytest tests/ -v
```

---

## Stage Checklist

| Stage | Goal | Tests Pass |
|---|---|---|
| 1 | Scaffolding & health check | [ ] |
| 2 | Board generation | [ ] |
| 3 | Game state model & serialization | [ ] |
| 4 | Valid moves engine | [ ] |
| 5 | Core API endpoints | [ ] |
| 6 | Win conditions | [ ] |
| 7 | Special tile effects | [ ] |
| 8 | AI minimax engine | [ ] |
| 9 | Frontend | [ ] |
| 10 | Polish & full integration | [ ] |
