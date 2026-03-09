# Domain Expansion — Development Plan

## Clarifications & Design Decisions

The following decisions were made before planning:

| Topic | Decision |
|---|---|
| Backend framework | Flask |
| Game state storage | SQLite (persistent across restarts) |
| Tower valid moves | 4 tiles only — one per cardinal axis at exactly 3 steps (not full Manhattan distance 3) |
| Barbarian trigger | On visibility — fires when it enters any player's visible area, including via Tower fog reveal at distance < 3 |
| Dominant win condition | Interpreted as: one player holds > 50% of claimable tiles AND the opponent has 0 valid moves remaining |
| Cave retention | Once a Cave is claimed, unclaimed Caves remain in the valid moves pool on subsequent turns until a Cave connection is made or the game ends |

---

## Stage 1 — Backend: Project Setup & Board Generation

### Goal
Stand up the Flask project skeleton and implement seeded, reproducible board generation. The board should be fully generated before any game logic runs.

### What to Build
- `backend/` directory with `main.py`, `game/board.py`, `game/state.py`, `seed.py`
- SQLite model for persisting game state (a serialized board + metadata row per game)
- Seeded RNG (`seed.py`) wrapping Python's `random.Random` with a fixed seed
- Board generation in `board.py`:
  - Place Mountains (10–20% of tiles, randomly seeded)
  - Place special tiles: exactly 1 Wizard, 1–3 Barbarian groups, even number of Caves (min 2), Towers, Plains — quantities scaled with board size
  - Fill remaining non-special tiles with Forest
  - Place `domain_tiles_per_player` starting Domain tiles per player — not on Mountains or specials, not adjacent to each other
- `POST /game/new` endpoint accepting `{ width, height, seed, difficulty, domain_tiles_per_player }` and returning initial game state JSON (Section 12 shape)

### Tests (must all pass before Stage 2)
- Same seed always produces the same board (idempotency test)
- Mountain count is 10–20% of total tiles
- Exactly 1 Wizard tile present
- Cave count is even and >= 2
- Starting Domain tiles are not on Mountains/specials and not adjacent to each other
- Board dimensions match requested width/height
- API: `POST /game/new` returns 200 with expected JSON fields

---

## Stage 2 — Backend: Game State & Basic Valid Moves

### Goal
Implement the game state model and valid moves computation for Forest and Domain tiles. Fog of War state should be computed correctly from the valid moves pool.

### What to Build
- `game/state.py`: `GameState` class holding:
  - Board grid (2D array of tile objects)
  - Per-player: claimed tile set, valid moves pool, fog visibility set
  - Turn indicator, scores, game status
  - Wizard held-by tracker
- Valid moves logic in `game/rules.py`:
  - On claiming Forest or Domain: add all cardinally adjacent non-Mountain unclaimed tiles to that player's valid moves pool
  - A tile in the valid moves pool is "visible" (fog lifted)
  - When a tile is claimed, remove it from both players' valid moves pools
- `GET /game/{id}` — return serialized game state
- `GET /game/{id}/valid-moves` — return current valid moves for the active player

### Tests (must all pass before Stage 3)
- Claiming a Forest tile adds correct cardinal neighbors to valid moves pool
- Claiming a Domain tile behaves identically to Forest
- Claimed tiles are removed from both players' valid moves pools
- Fog correctly obscures tiles not in any pool and not claimed
- Starting Domain tiles seed the initial valid moves pools correctly
- API: `GET /game/{id}` returns correct board and valid_moves after a Forest claim

---

## Stage 3 — Backend: Special Tile Logic

### Goal
Implement all six special tile types and their effects on game state. This is the most complex backend stage — each tile type should be implemented and tested in isolation before integration.

### What to Build (one sub-section per tile type)

#### 3A — Plains
- On claim: collect all unclaimed non-Mountain tiles within Manhattan distance 1–2 (includes cardinals at distance 1 and 2, and diagonals at distance 2)
- Player picks **one tile** from those candidates; that tile is claimed
- State tracks "plains_first_pick" phase with valid pick candidates

#### 3B — Tower
- On claim: lift fog for all tiles within Manhattan distance ≤ 3 (all tiles reachable in ≤ 3 steps)
- Add to valid moves pool: only the 4 cardinal-axis tiles exactly 3 steps away (up, down, left, right), skipping Mountains
- Check for Barbarian visibility trigger in newly revealed tiles (see 3E)

#### 3C — Cave
- On claim: add all other unclaimed (non-inert) Cave tiles to the claimant's valid moves pool
- Track "last_cave_claimed_by" in state
- If the claimant's next move is another Cave: mark both Caves as connected (inert), remove ability
- If the claimant's next move is anything else: Cave retains ability; unclaimed Caves stay in pool
- Inert/connected Caves do not appear as Cave destinations

#### 3D — Wizard
- Wizard tile is subject to fog of war like all other tiles
- On claim: set `wizard_held_by` to claiming player
- On a future turn, player may teleport to any unclaimed, non-Mountain tile as their move
- After teleport: `wizard_held_by = null`; Wizard tile marked as used (`wizard_used` state)
- Track wizard-move intent separately from normal moves

#### 3E — Barbarian
- Each Barbarian group has a seeded direction (horizontal/vertical) assigned at board generation
- Trigger condition: Barbarian tile becomes visible (enters any player's visibility set)
  - This includes being added to a valid moves pool AND being revealed by Tower fog at distance < 3
- On trigger:
  - Sweep the assigned row or column: unclaim all tiles in path (restore to neutral Forest); Mountains are passed through but remain unclaimed and unclaimable
  - Barbarian tile itself is replaced with a standard claimable Forest tile
  - Update both players' valid moves pools and fog state after the sweep

### Tests (must all pass before Stage 4)
- **Plains**: correct single-pick flow; edge case with no available picks; state machine transitions correct
- **Tower**: exactly 4 cardinal-axis valid moves added (or fewer at edges); fog revealed for all tiles within distance 3; Barbarian in Tower's fog zone triggers correctly
- **Cave**: connection made when next move is a Cave; connection NOT made when next move is something else; inert Caves excluded from valid moves pool
- **Wizard**: tile hidden by fog on initial board; `wizard_held_by` set on claim; teleport move is legal to any unclaimed non-Mountain tile; consumed after use
- **Barbarian**: fires on entering valid moves pool; fires on Tower reveal at distance < 3; correct row/column swept; Barbarian tile becomes Forest afterwards; both players' pools updated after sweep
- **Integration**: a single game exercising all tile types in sequence without state corruption

---

## Stage 4 — Backend: Turn Flow & Win Conditions

### Goal
Wire the full turn pipeline into the `/move` endpoint. This stage makes the game playable end-to-end without a frontend.

### What to Build
- `POST /game/{id}/move` endpoint accepting `{ row, col }` (and optionally `{ wizard: true }` for wizard teleport)
  1. Validate the move is in the current player's valid moves pool (or is a wizard teleport)
  2. Claim the tile
  3. Apply tile-type effects (resolving special tiles, updating pools, checking Barbarian triggers)
  4. Check win conditions (see below)
  5. If no special sub-phase pending (Plains, Cave prompt), advance turn to next player
- Win condition checks in `game/rules.py`:
  - **Standard end**: all claimable tiles claimed → game over, compare scores
  - **Dominant end**: one player has > 50% of all claimable tiles AND opponent has 0 valid moves → that player wins
  - Ties possible in standard end
- Turn skipping: if the active player has 0 valid moves and the game has not ended, skip their turn (opponent plays again)

### Tests (must all pass before Stage 5)
- Valid move accepted; invalid move (not in pool) rejected with 400
- Claiming a Mountain-position move rejected
- Standard end triggers when all tiles claimed
- Dominant end triggers when > 50% owned and opponent pool is empty
- Tie correctly detected
- Turn advances to opponent after a normal move
- Turn stays with current player during Plains sub-phase (one bonus pick)
- Turn stays if pending Cave connection (player chose Cave and next pick should confirm connection or not)
- Turn skip when active player has no valid moves
- Wizard teleport move flows through correctly

---

## Stage 5 — Backend: AI Engine

### Goal
Implement the minimax AI with alpha-beta pruning and expose it via the `/ai-move` endpoint.

### What to Build
- `game/ai/heuristic.py`: evaluation function
  - Tile count delta (AI − human)
  - Valid moves pool size delta (AI − human)
  - Bonus for special tiles (Wizard > Tower > Cave > Plains) in or near AI pool
  - Penalty if a Barbarian is in or near AI territory (would damage AI tiles)
  - Bonus for connected Caves
- `game/ai/minimax.py`: minimax with alpha-beta pruning
  - Difficulty → search depth: Easy = 2, Medium = 4, Hard = 6
  - Move ordering: special tiles first (Wizard > Tower > Cave > Plains > Forest/Domain), then moves that expand the pool most
  - Plains handling: enumerate all valid picks (Manhattan distance 1–2) as a single compound node
  - Wizard handling: evaluate wizard teleport as an alternative move on any AI turn
  - Return best move(s) to apply
- `POST /game/{id}/ai-move` endpoint: runs minimax, applies result, returns updated state

### Tests (must all pass before Stage 6)
- AI always returns a move that is in the valid moves pool (no illegal AI moves)
- Easy AI has shallower search than Hard (verify depth limit is respected)
- AI correctly handles Plains bonus pick (single pick applied in one turn)
- AI correctly uses Wizard teleport when it holds the ability
- Heuristic returns higher score when AI has more tiles
- Alpha-beta produces the same result as unoptimized minimax (correctness check on small boards)
- AI move endpoint returns updated game state in expected JSON shape

---

## Stage 6 — Frontend: Project Setup & Board Rendering

### Goal
Bootstrap the React app and render the game board with placeholder colors. The frontend should be able to start a game and display the board without interactive moves yet.

### What to Build
- React project with Vite under `frontend/`
- `src/assets/assetMap.js` — maps logical tile keys (e.g., `"forest_player"`) to placeholder colors (or PNG paths later)
- `src/components/Tile.jsx` — renders a single tile using assetMap; accepts tile state as props
- `src/components/Board.jsx` — renders the 2D grid of Tile components; scales to viewport
- `src/components/FogOverlay.jsx` — renders the fog overlay on obscured tiles
- `src/api.js` — wraps all fetch calls to the backend (`newGame`, `getState`, `getValidMoves`, `submitMove`, `triggerAiMove`)
- Pre-game setup screen (`App.jsx` or `SetupScreen.jsx`):
  - Width input (6–24), Height input (6–20), Seed input (optional), Difficulty selector, Start Game button

### Tests (must all pass before Stage 7)
- Setup screen form validates min/max for width and height
- Submitting setup screen calls `POST /game/new` and renders the board
- All tile types render with their correct placeholder color
- Fog tiles render as dark overlay
- Wizard tile is hidden by fog of war like all other tiles
- Board scales correctly for a 12×10 default board and a 24×20 large board

---

## Stage 7 — Frontend: Game Interaction & AI Turn

### Goal
Make the game fully playable from the browser. Human clicks tiles, AI takes its turn, HUD updates, game ends with a modal.

### What to Build
- Valid move highlighting — fetch `/game/{id}/valid-moves`, render `valid_move` overlay on those tiles
- Click handler on Tile: only fires if tile is in valid moves pool; calls `POST /game/{id}/move`; re-fetches state
- `src/components/HUD.jsx`:
  - Current turn indicator (Human / AI)
  - Score display (Human count vs AI count)
  - Remaining claimable tiles count
  - Wizard ability indicator (highlight if either player holds it)
  - Seed display
- AI turn flow:
  - After human move, if status is still `in_progress` and turn is AI: board becomes non-interactive, show "AI is thinking..." indicator, call `POST /game/{id}/ai-move`, re-fetch state
- End game modal: display winner, final scores, "Play Again" / "New Game" buttons

### Tests (must all pass before Stage 8)
- Clicking a non-highlighted tile does nothing
- Clicking a highlighted tile sends the correct `{ row, col }` to the backend
- HUD scores update after each move
- AI "thinking" indicator appears and disappears correctly
- End game modal displays correct winner text
- "Play Again" restarts with the same seed; "New Game" returns to setup screen

---

## Stage 8 — Frontend: Special Tile UX

### Goal
Implement the multi-step interaction flows for Plains, Cave, and Wizard. These require temporary UI state machines on the frontend.

### What to Build
- **Plains bonus pick**:
  - After claiming a Plains tile, backend returns state with `phase: "plains_first_pick"` and valid moves = all unclaimed non-Mountain tiles within Manhattan distance 1–2
  - UI prompts "Select your bonus tile" with those tiles highlighted
  - After pick: normal turn advance
- **Cave selection**:
  - After claiming a Cave, if other unclaimed Caves exist, they are highlighted as valid moves alongside normal moves
  - UI does not force Cave selection — player may choose any valid move next turn
  - No special prompt needed beyond the existing highlighting
- **Wizard activation**:
  - If human holds Wizard, show "Use Wizard" button in HUD
  - Clicking it enters "wizard mode": all unclaimed non-Mountain tiles become highlighted
  - Clicking one submits `POST /game/{id}/move` with `{ wizard: true, row, col }`
  - Cancel button exits wizard mode without using the ability
- **Barbarian charge visual**:
  - When the AI or human triggers a Barbarian, the re-fetched state will show the swept row/column as unclaimed
  - Briefly flash the affected tiles before settling on the new state (CSS transition or brief highlight)

### Tests (must all pass before Stage 9)
- Plains: after claiming Plains, UI shows all unclaimed non-Mountain tiles within Manhattan distance 1–2 as valid picks
- Cave: Cave destinations highlighted alongside normal valid moves after Cave claim
- Wizard button appears only when human holds the ability; disappears after use
- Wizard mode highlights all unclaimed non-Mountain tiles
- Cancel wizard exits mode cleanly without submitting a move
- Barbarian flash animation fires when swept tiles are detected in new state

---

## Stage 9 — Integration, Polish & End-to-End Testing

### Goal
Verify the full system works correctly end-to-end across all game paths. Fix rough edges and validate edge cases.

### What to Build / Fix
- AI thinking time cap: configurable timeout in minimax (default 5s for Hard); if exceeded, return best move found so far
- Error handling: API errors surface as toast/banner in the UI rather than silent failures
- Asset swap: confirm `assetMap.js` hot-swap works by replacing one placeholder with a real PNG without touching component logic
- Seed sharing: seed displayed in HUD; copy-to-clipboard button

### End-to-End Tests
- **Full game — standard end**: play a complete game (using AI on Easy) until all tiles are claimed; verify winner is determined correctly
- **Full game — dominant end**: construct a board state where one player reaches > 50% with no valid moves for opponent; verify dominant win fires
- **Barbarian trigger via Tower**: set up a board where a Tower reveal exposes a Barbarian within distance < 3; verify Barbarian fires immediately on Tower claim
- **Wizard used by AI**: verify AI correctly uses Wizard teleport and it cannot be used again
- **Cave chain**: claim a Cave, then claim another Cave; verify both become inert and subsequent moves no longer list them as Cave destinations
- **Plains edge case**: claim a Plains tile on the board edge where no bonus tiles exist; verify turn advances normally with no pick phase
- **Seed reproducibility**: start two games with the same seed and config; verify identical board layouts and identical AI move sequences
- **Large board performance**: 24×20 board on Hard difficulty; AI move must complete within the time cap
- **UI error path**: send a malformed move to the backend; verify the frontend displays an error and the game remains playable

---

## Summary Timeline

| Stage | Focus | Key Exit Criteria |
|---|---|---|
| 1 | Board generation | Seeded board is reproducible; tile counts in spec |
| 2 | Valid moves + fog | Forest/Domain adjacency correct; fog reflects pool |
| 3 | Special tile logic | All 6 tile types tested in isolation |
| 4 | Turn flow + win | Full turn pipeline; both win conditions fire |
| 5 | AI engine | AI never makes illegal moves; alpha-beta matches minimax |
| 6 | React board render | Board visible with correct placeholder colors |
| 7 | Interactive game | Human can play a full game vs AI through the browser |
| 8 | Special tile UX | Plains/Cave/Wizard flows all work in the UI |
| 9 | Integration + E2E | Full game paths pass; performance acceptable |
