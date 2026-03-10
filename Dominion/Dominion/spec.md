# Domain Expansion — Game Specification

## 1. Overview

**Domain Expansion** is a 1v1 turn-based strategy game played on a procedurally generated grid board. Each player expands their claimed territory by selecting valid tiles each turn. The game ends when all claimable tiles are taken, or when one player controls more than half of the available tiles and the opponent has no moves that can overwrite them. The player with the most claimed tiles wins.

One player is a human; the other is an AI opponent driven by the **minimax algorithm with alpha-beta pruning**.

---

## 2. Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React (pixel-art styled UI) |
| Backend | Python (FastAPI or Flask) |
| AI Engine | Python (minimax + alpha-beta pruning) |
| State | Backend-authoritative; frontend is a thin client |
| Communication | REST API (JSON) |

---

## 3. Project Structure

```
/
├── backend/
│   ├── main.py               # API entry point
│   ├── game/
│   │   ├── board.py          # Board generation, tile logic
│   │   ├── rules.py          # Valid move computation
│   │   ├── state.py          # Game state model
│   │   └── ai/
│   │       ├── minimax.py    # Minimax + alpha-beta
│   │       └── heuristic.py  # Scoring/evaluation functions
│   └── seed.py               # Seeded RNG for board generation
│
└── frontend/
    ├── src/
    │   ├── components/
    │   │   ├── Board.jsx         # Grid renderer
    │   │   ├── Tile.jsx          # Individual tile renderer
    │   │   ├── HUD.jsx           # Score, turn indicator, controls
    │   │   └── FogOverlay.jsx    # Fog of War overlay
    │   ├── assets/
    │   │   └── tiles/            # Pixel art assets (see Section 10)
    │   ├── App.jsx
    │   └── api.js                # Backend API calls
    └── public/
```

---

## 4. Board Generation

### 4.1 Parameters
Board configuration is set at game start and includes:

| Parameter | Description | Default |
|---|---|---|
| `width` | Number of columns | 12 |
| `height` | Number of rows | 10 |
| `seed` | Integer seed for RNG | Random if not provided |
| `difficulty` | AI difficulty level | `medium` |
| `domain_tiles_per_player` | Starting Domain tiles each | 2 |

Width, height, and seed should all be user-configurable via a pre-game lobby/setup screen.

### 4.2 Generation Algorithm
Using the seed, the backend generates the full board using a seeded RNG:
1. Place **Mountains** — randomly distributed, never claimable. Roughly 10–20% of tiles.
2. Place **special tiles** — Wizard (exactly 1), Barbarian groups (1–3), Caves (even number, minimum 2), Towers, Plains. Quantities scale with board size.
3. Remaining tiles are **Forest**.
4. Place **starting Domain tiles** for each player — randomly placed, seeded, guaranteed not to be Mountains or special tiles, and not adjacent to each other.

The same seed always produces the same board.

---

## 5. Tile Types

### 5.1 Summary Table

| Tile | Claimable | Special Ability |
|---|---|---|
| Domain | Yes | Same as Forest (cardinal adjacency) |
| Forest | Yes | Adds cardinally adjacent tiles to valid moves |
| Plains | Yes | Grants a 2-step move (see 5.4) |
| Tower | Yes | Reveals tiles within 3 moves; only allows moves at exactly distance 3 |
| Cave | Yes | Teleports to any other unclaimed Cave; connected Caves go inert |
| Mountain | **No** | Impassable; never claimable; excluded from tile count |
| Wizard | Yes | One-time teleport to any unclaimed tile on the board |
| Barbarians | Yes (after charge) | Charges across entire board row/column on reveal, unclaiming all tiles in path |

### 5.2 Forest & Domain
When a player claims a Forest or Domain tile, all **cardinally adjacent** tiles (up, down, left, right) that are not Mountains are added to that player's **valid moves pool** if not already claimed.

### 5.3 Tower
When a player claims a Tower tile:
- **Fog of War is lifted** for all tiles within a Manhattan distance of 3 from the Tower (i.e., all tiles reachable in up to 3 cardinal steps), revealing their types.
- **Valid moves added**: Only tiles at **exactly Manhattan distance 3** from the Tower are added to the valid moves pool. Tiles at distances 1 and 2 are revealed but not added as valid moves by the Tower itself (they may still be valid from other claimed tiles).
- Paths to distance-3 tiles must follow cardinal directions away from the Tower (no backtracking).

### 5.4 Plains
When a player claims a Plains tile:
- **Fog of War is lifted** for all tiles within a Manhattan distance of 2 from the Plains (i.e., all tiles reachable in up to 2 cardinal steps), revealing their types.
- **Valid moves added**: Only tiles at **of at least Manhattan distance 2** from the Plains are added to the valid moves pool.

### 5.5 Cave
- When a player claims a Cave tile, all **other unclaimed Cave tiles** on the board are added to their valid moves pool.
- If the player then uses their next move to claim one of those Caves, the two Caves become **connected**:
  - Both Caves are now claimed by this player and count toward their score.
  - Both Caves lose their special ability and are treated as ordinary claimed tiles (no longer add other Caves to valid moves).
- If a Cave is claimed but the player does not subsequently claim another Cave (e.g., they claim a different tile instead), the Cave connection is not made, and the Cave retains its ability for future turns.
- Already-connected Caves do not appear in any player's valid moves pool as Cave destinations.

### 5.6 Wizard
- The Wizard tile appears **once** on the board and is visible through Fog of War (not obscured).
- When a player claims the Wizard tile, they immediately receive a **one-time-use teleport ability**.
- On any future turn, instead of making a normal move, the player may activate the Wizard ability to **teleport to any unclaimed, non-Mountain tile** on the board and claim it.
- After the teleport is used, the Wizard ability is consumed and cannot be used again. The Wizard tile itself remains claimed by that player.
- If the Wizard tile is never claimed, neither player gets the ability.

### 5.7 Barbarians
- Barbarian tiles appear on the board and are **not claimable while active**.
- When a Barbarian tile is **revealed from the Fog of War** (i.e., it enters any player's visible area), it **instantly triggers**:
  1. The Barbarians pick the direction with the longest path possible, either horizontal or vertical.
  2. The Barbarians charge across the **entire row or column** in that direction from their starting position, unclaiming every tile they pass through (regardless of which player owns it, and including Mountains — Mountains are passed through but remain unclaimed and unclaimable).
  3. All unclaimed tiles left in the Barbarians' wake become open and can be reclaimed by either player on future turns.
  4. After charging, the Barbarian tile itself is removed from the board and the tiles it occupied become standard claimable tiles (Forest).
- Multiple Barbarian groups on the board each trigger independently when revealed.
- A row/column may be hit more than once if multiple Barbarian groups are assigned to it.

---

## 6. Valid Moves & Fog of War

### 6.1 Valid Moves Pool
Each player maintains a **valid moves pool** — a set of tile coordinates they are allowed to claim on their turn. This pool is computed dynamically from all currently claimed tiles and their tile-type rules (see Section 5).

- A tile can only be in the valid moves pool if it is **not already claimed** by either player and is **not a Mountain**.
- When a tile is claimed, it is removed from both players' valid moves pools if present, and new tiles may be added based on the tile's type.
- Every move that is added to the valid moves list also tracks what tile type generated it. When a tile is claimed on a players turn, the tile is validated based on the tile that generated it. i.e. if a Cave tile is added to the valid moves list by another Cave, and that new Cave is claimed on the next turn, then the claimed Cave determines it was only valid via a Cave, and both Caves are considered connected. However, if that Cave is also valid by a forest or other non-single-use tile, than the permanent tile takes priority and the existing Cave is not used up

### 6.2 Fog of War
- All tiles not in either player's valid moves pool (and not already claimed) are **obscured by Fog of War**.
- The frontend renders fogged tiles as obscured (darkened placeholder sprite). Their tile type is not revealed until fog is lifted.
- Fog is lifted from a tile when it enters a player's valid moves pool or is claimed.
- The Tower tile lifts fog for all tiles within Manhattan distance 3 upon being claimed (see 5.3).

---

## 7. Turn Structure

1. The **current player's valid moves** are highlighted on the board.
2. The player selects one valid tile to claim.
3. The backend processes the move:
   - Marks the tile as claimed by this player.
   - Updates both players' valid move pools.
   - Checks for Barbarian reveals.
   - Checks win conditions.
4. Special tile effects are resolved (Plains bonus move, Cave connection prompt, Wizard activation, Barbarian charge).
5. Turn passes to the other player.

**Turn order**: Human player goes first. Configurable at game start.

---

## 8. Win Conditions

- **Standard end**: When all claimable tiles (excluding Mountains) have been claimed by either player, the game ends. The player with the most claimed tiles wins. Ties are possible.
- **Dominant end**: If one player controls more than half of all claimable tiles (excluding Mountains) and the opponent has **no valid moves that could overwrite those tiles**, the game ends immediately and that player wins.
- Mountains are **always excluded** from the total tile count used in win condition calculations.

---

## 9. AI — Minimax with Alpha-Beta Pruning

### 9.1 Difficulty Levels

| Difficulty | Minimax Search Depth | Notes |
|---|---|---|
| Easy | 2 | Shallow lookahead; may make suboptimal moves |
| Medium | 4 | Moderate lookahead; plays competently |
| Hard | 6 | Deep lookahead; plays near-optimally |

### 9.2 Heuristic / Evaluation Function
The board evaluation function scores a game state from the AI's perspective. Suggested components (implementer may tune weights):

- **Tile count delta**: AI claimed tiles minus human claimed tiles.
- **Valid moves delta**: Size of AI valid moves pool minus human valid moves pool (territory potential).
- **Special tile proximity**: Bonus for having high-value tiles (Wizard, Tower, Cave) in or near the valid moves pool.
- **Barbarian threat**: Penalty if a Barbarian is close to being revealed (within the AI's visible area) and would harm the AI's tiles.
- **Cave connectivity bonus**: Bonus for having Caves that are connected (locked in, scoring normally).

### 9.3 Move Ordering
To improve alpha-beta pruning efficiency, moves should be ordered before evaluation:
1. Moves that claim special tiles first (Wizard > Tower > Cave > Plains > Forest/Domain).
2. Moves that expand the valid moves pool the most.

### 9.4 Plains Handling in Minimax
Because Plains triggers a 2-step move, the AI must evaluate the Plains turn as a **compound action** (first pick + second pick) in a single minimax node, enumerating all valid (first pick, second pick) pairs.

### 9.5 Wizard Handling in Minimax
The AI must track whether it holds the Wizard ability and evaluate using it as an alternative to a normal move on any given turn.

---

## 10. Asset System (Pixel Art)

### 10.1 Structure
All tile sprites are stored in:
```
frontend/src/assets/tiles/
```

Each tile type has the following sprite variants as PNG files:

| Filename | Description |
|---|---|
| `forest_neutral.png` | Unclaimed Forest tile |
| `forest_player.png` | Forest tile claimed by human |
| `forest_ai.png` | Forest tile claimed by AI |
| `plains_neutral.png` | Unclaimed Plains tile |
| `plains_player.png` | Plains tile claimed by human |
| `plains_ai.png` | Plains tile claimed by AI |
| `tower_neutral.png` | Unclaimed Tower tile |
| `tower_player.png` | Tower tile claimed by human |
| `tower_ai.png` | Tower tile claimed by AI |
| `cave_neutral.png` | Unclaimed Cave tile |
| `cave_player.png` | Cave tile claimed by human |
| `cave_ai.png` | Cave tile claimed by AI |
| `cave_inert_player.png` | Connected (inert) Cave, human |
| `cave_inert_ai.png` | Connected (inert) Cave, AI |
| `mountain.png` | Mountain tile (never changes) |
| `wizard.png` | Wizard tile (always visible) |
| `wizard_used.png` | Wizard tile after ability is consumed |
| `barbarian.png` | Active Barbarian tile |
| `domain_player.png` | Starting Domain tile, human |
| `domain_ai.png` | Starting Domain tile, AI |
| `fog.png` | Fog of War overlay tile |
| `valid_move.png` | Valid move highlight overlay |

### 10.2 Placeholder System
Until final art is provided, the frontend should render **colored placeholder tiles** using a simple color mapping:

| Tile State | Placeholder Color |
|---|---|
| Neutral Forest | `#3a7d44` |
| Player claimed | `#4a90d9` |
| AI claimed | `#d94a4a` |
| Mountain | `#6b6b6b` |
| Wizard | `#c9a84c` |
| Barbarian | `#8b0000` |
| Cave | `#7b5ea7` |
| Plains | `#c4a35a` |
| Tower | `#5a8fa3` |
| Fog of War | `#1a1a2e` |
| Valid move highlight | Semi-transparent `#ffffff` at 30% opacity |

### 10.3 Swapping Assets
The `Tile.jsx` component should reference sprites by a **logical tile key** (e.g., `"forest_player"`) resolved through a central `assetMap.js` file. To swap in real pixel art, only `assetMap.js` needs to be updated — no component logic changes required.

```
frontend/src/assets/assetMap.js   ← single source of truth for all sprite paths
```

### 10.4 Tile Render Size
Tiles should be rendered at **32×32px** by default, scaling with board size to fit the viewport. Support for a 16×16px compact mode for larger boards.

---

## 11. UI / UX

### 11.1 Pre-Game Setup Screen
- Board width input (min 6, max 24)
- Board height input (min 6, max 20)
- Seed input (optional; random if blank)
- Difficulty selector (Easy / Medium / Hard)
- "Start Game" button

### 11.2 Game Screen Layout
- **Board**: Central element; fills majority of screen.
- **HUD (top or side panel)**:
  - Current turn indicator (Human / AI)
  - Score display (Human tile count vs AI tile count)
  - Remaining claimable tiles count
  - Wizard ability indicator (if held by either player)
  - Seed display (for sharing/replayability)
- **End Game Modal**: Displays winner, final scores, and a "Play Again" / "New Game" button.

### 11.3 Interaction
- Valid move tiles are highlighted with the `valid_move` overlay.
- Clicking a highlighted tile submits the move to the backend.
- During the AI's turn, the board is non-interactive. A visual indicator shows the AI is "thinking."
- Plains bonus move: after the Plains tile is claimed, the UI enters a two-step selection mode, prompting the player to pick their first then second bonus tile.
- Cave selection: after claiming a Cave, if other unclaimed Caves exist, the valid moves highlights update to show Cave destinations. The player may choose a Cave or any other valid move on their next turn.

---

## 12. API Endpoints (Backend)

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/game/new` | Start a new game; accepts config params; returns initial game state |
| `GET` | `/game/{id}` | Get current game state |
| `POST` | `/game/{id}/move` | Submit a human player move; returns updated state |
| `POST` | `/game/{id}/ai-move` | Trigger AI to compute and apply its move; returns updated state |
| `GET` | `/game/{id}/valid-moves` | Get current valid moves for the active player |

### Game State Response Shape (JSON)
```json
{
  "game_id": "string",
  "board": [
    [{ "type": "forest", "owner": null, "visible": true }, ...]
  ],
  "valid_moves": [[row, col], ...],
  "scores": { "human": 12, "ai": 9 },
  "turn": "human",
  "status": "in_progress",
  "wizard_held_by": null,
  "seed": 123456,
  "width": 12,
  "height": 10
}
```

---

## 13. Open Questions / Future Considerations

- **Multiplayer**: The spec covers only human vs. AI. Human vs. human (local or networked) is out of scope for now.
- **Barbarian direction assignment**: Currently resolved at board generation time via seeded RNG. Could be made partially random at trigger time in the future.
- **Undo**: No undo mechanic specified. May be added later for the human player only.
- **Animation**: Barbarian charge and Wizard teleport may benefit from simple tile-sweep or flash animations. Not required for initial implementation.
- **AI thinking time cap**: Consider adding a configurable timeout for the AI move computation to prevent long waits on Hard difficulty with large boards.