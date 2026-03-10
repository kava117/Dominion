from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game.state import GameState

CARDINAL_DELTAS = [(-1, 0), (1, 0), (0, -1), (0, 1)]

# Tile types whose claim behaviour expands the pool via cardinal adjacency
_FOREST_LIKE = {"forest", "domain"}


def cardinal_neighbors(r: int, c: int, height: int, width: int) -> list[tuple[int, int]]:
    return [
        (r + dr, c + dc)
        for dr, dc in CARDINAL_DELTAS
        if 0 <= r + dr < height and 0 <= c + dc < width
    ]


def compute_initial_valid_moves(board: list, height: int, width: int) -> dict:
    """Seed both players' valid moves pools from their starting Domain tiles.

    Forest/Domain rule: cardinally adjacent tiles that are unclaimed and not Mountains.
    """
    pools:     dict[str, list] = {"human": [], "ai": []}
    pool_sets: dict[str, set]  = {"human": set(), "ai": set()}

    for r in range(height):
        for c in range(width):
            tile = board[r][c]
            if tile["type"] in ("domain", "forest") and tile["owner"] in ("human", "ai"):
                player = tile["owner"]
                for nr, nc in cardinal_neighbors(r, c, height, width):
                    neighbor = board[nr][nc]
                    if neighbor["owner"] is None and neighbor["type"] != "mountain":
                        key = (nr, nc)
                        if key not in pool_sets[player]:
                            pool_sets[player].add(key)
                            pools[player].append([nr, nc])

    return pools


# ---------------------------------------------------------------------------
# Pool helpers
# ---------------------------------------------------------------------------

def _pool_as_set(pool: list) -> set[tuple[int, int]]:
    return {(pos[0], pos[1]) for pos in pool}


def remove_from_pools(state: "GameState", row: int, col: int) -> None:
    """Remove (row, col) from both players' valid moves pools."""
    for player in ("human", "ai"):
        state.data["valid_moves"][player] = [
            pos for pos in state.data["valid_moves"][player]
            if pos[0] != row or pos[1] != col
        ]


def expand_pool_forest(state: "GameState", row: int, col: int, player: str) -> None:
    """Forest/Domain effect: add unclaimed, non-mountain cardinal neighbors to player's pool."""
    pool     = state.data["valid_moves"][player]
    pool_set = _pool_as_set(pool)

    for nr, nc in cardinal_neighbors(row, col, state.height, state.width):
        neighbor = state.tile(nr, nc)
        if neighbor["owner"] is None and neighbor["type"] != "mountain":
            key = (nr, nc)
            if key not in pool_set:
                pool_set.add(key)
                pool.append([nr, nc])


# ---------------------------------------------------------------------------
# Move validation
# ---------------------------------------------------------------------------

def validate_move(state: "GameState", row: int, col: int) -> tuple[bool, str]:
    """Return (is_valid, reason) for a normal move by the current player."""
    if state.status != "in_progress":
        return False, "Game is not in progress"

    player = state.turn
    vm     = state.data["valid_moves"].get(player, [])

    if [row, col] not in vm:
        return False, "Tile is not in valid moves pool"

    tile = state.tile(row, col)
    if tile["type"] == "mountain":
        return False, "Mountains cannot be claimed"
    if tile["owner"] is not None:
        return False, "Tile is already claimed"

    return True, "OK"


# ---------------------------------------------------------------------------
# Move application
# ---------------------------------------------------------------------------

def _apply_tile_effect(
    state: "GameState",
    row: int,
    col: int,
    player: str,
    tile_type: str,
    in_plains_sub_move: bool = False,
) -> None:
    """Dispatch to the correct tile-type effect handler.

    in_plains_sub_move=True suppresses nested Plains phases.
    """
    # Import here to avoid circular imports (effects.py imports from rules.py)
    from game import effects

    if tile_type in _FOREST_LIKE:
        expand_pool_forest(state, row, col, player)
    elif tile_type == "plains":
        if in_plains_sub_move:
            # Plains-within-Plains: treat as Forest (no nested bonus move)
            expand_pool_forest(state, row, col, player)
        else:
            effects.apply_plains(state, row, col, player)
    elif tile_type == "tower":
        effects.apply_tower(state, row, col, player)
    elif tile_type == "cave":
        effects.apply_cave(state, row, col, player)
    elif tile_type == "wizard":
        effects.apply_wizard(state, row, col, player)
    # Barbarian: not claimable while active; no effect handler needed here.
    # After triggering the Barbarian tile becomes Forest (handled in effects.py).


def _claim_tile(
    state: "GameState",
    row: int,
    col: int,
    player: str,
    in_plains_sub_move: bool = False,
) -> str:
    """Core tile-claiming logic without turn advancement.

    Returns the tile type claimed.  Called by apply_move and Plains sub-picks.
    """
    tile      = state.data["board"][row][col]
    tile_type = tile["type"]

    tile["owner"] = player
    state.data["scores"][player] += 1
    remove_from_pools(state, row, col)
    _apply_tile_effect(state, row, col, player, tile_type, in_plains_sub_move)

    return tile_type


def apply_move(state: "GameState", row: int, col: int) -> str:
    """Claim (row, col) for the current player, update pools, advance turn.

    Returns the tile type claimed.  Does NOT advance the turn when a Plains
    phase is started (the Plains sub-moves handle their own turn advance).
    """
    from game.win import check_win

    player    = state.data["turn"]
    tile_type = _claim_tile(state, row, col, player)

    # Only advance if no special phase was set by the tile effect
    if not state.data.get("_plains_pending"):
        state.data["turn"] = "ai" if player == "human" else "human"
        check_win(state)

    return tile_type


# ---------------------------------------------------------------------------
# Fog visibility
# ---------------------------------------------------------------------------

def compute_visible(state: "GameState") -> set[tuple[int, int]]:
    """Return the set of tile positions that are not in fog.

    A tile is visible if:
    - It is claimed (owner is not None)
    - It is a Mountain (fixed terrain, always shown)
    - It is in either player's valid moves pool
    - It has been explicitly Tower-revealed (revealed_extra)
    """
    visible: set[tuple[int, int]] = set()

    for r in range(state.height):
        for c in range(state.width):
            tile = state.tile(r, c)
            # Mountains always visible; Wizard always visible per spec §5.6
            if tile["owner"] is not None or tile["type"] in ("mountain", "wizard"):
                visible.add((r, c))

    for player_pool in state.valid_moves.values():
        for pos in player_pool:
            visible.add((pos[0], pos[1]))

    for pos in state.data.get("revealed_extra", []):
        visible.add((pos[0], pos[1]))

    # Plains valid picks are the player's valid moves during the plains phase
    if state.phase == "plains_pick":
        for pos in state.phase_data.get("valid_picks", []):
            visible.add((pos[0], pos[1]))

    return visible
