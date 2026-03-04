"""Special tile effects — Plains, Tower, Cave, Wizard, Barbarian.

Each public function is called from rules._apply_tile_effect() after a tile
is claimed.  All functions mutate the GameState in-place.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game.state import GameState

from game.rules import (
    CARDINAL_DELTAS,
    cardinal_neighbors,
    remove_from_pools,
    expand_pool_forest,
    _pool_as_set,
)


# ---------------------------------------------------------------------------
# Plains
# ---------------------------------------------------------------------------

def plains_first_picks(state: "GameState", row: int, col: int) -> list[list[int]]:
    """Compute valid first-pick candidates for a Plains tile at (row, col).

    Spec: tiles at exactly cardinal distance 2 (one per cardinal direction),
    unclaimed and non-Mountain.
    """
    picks = []
    for dr, dc in CARDINAL_DELTAS:
        nr, nc = row + dr * 2, col + dc * 2
        if 0 <= nr < state.height and 0 <= nc < state.width:
            t = state.tile(nr, nc)
            if t["owner"] is None and t["type"] != "mountain":
                picks.append([nr, nc])
    return picks


def apply_plains(state: "GameState", row: int, col: int, _player: str) -> None:
    """Enter the Plains bonus-move flow (or skip it if no picks exist)."""
    first_picks = plains_first_picks(state, row, col)

    if not first_picks:
        # No bonus tiles available — turn advances normally (caller handles this)
        return

    state.data["phase"] = "plains_first_pick"
    state.data["phase_data"] = {
        "plains_pos":  [row, col],
        "valid_picks": first_picks,
    }
    # Turn does NOT advance yet — set a sentinel so apply_move knows to skip it
    state.data["_plains_pending"] = True


def apply_plains_first_pick(state: "GameState", row: int, col: int) -> None:
    """Claim the first Plains bonus tile and set up the second-pick phase."""
    from game.rules import _claim_tile  # local import to avoid circular dep

    player = state.data["turn"]
    _claim_tile(state, row, col, player, in_plains_sub_move=True)

    # Compute second picks: unclaimed, non-Mountain cardinal neighbors of first pick
    second_picks = [
        [nr, nc]
        for nr, nc in cardinal_neighbors(row, col, state.height, state.width)
        if state.tile(nr, nc)["owner"] is None
        and state.tile(nr, nc)["type"] != "mountain"
    ]

    if not second_picks:
        _end_plains(state)
        return

    state.data["phase"] = "plains_second_pick"
    state.data["phase_data"] = {
        "first_pick_pos": [row, col],
        "valid_picks":    second_picks,
    }


def apply_plains_second_pick(state: "GameState", row: int, col: int) -> None:
    """Claim the second Plains bonus tile and end the Plains phase."""
    from game.rules import _claim_tile

    player = state.data["turn"]
    _claim_tile(state, row, col, player, in_plains_sub_move=True)
    _end_plains(state)


def _end_plains(state: "GameState") -> None:
    from game.win import check_win
    state.data["phase"]             = None
    state.data["phase_data"]        = {}
    state.data.pop("_plains_pending", None)
    player = state.data["turn"]
    state.data["turn"] = "ai" if player == "human" else "human"
    check_win(state)


def validate_plains_pick(state: "GameState", row: int, col: int) -> tuple[bool, str]:
    valid_picks = state.data.get("phase_data", {}).get("valid_picks", [])
    if [row, col] not in valid_picks:
        return False, "Not a valid Plains bonus pick"
    t = state.tile(row, col)
    if t["owner"] is not None:
        return False, "Tile already claimed"
    if t["type"] == "mountain":
        return False, "Cannot claim a mountain"
    return True, "OK"


# ---------------------------------------------------------------------------
# Tower
# ---------------------------------------------------------------------------

def apply_tower(state: "GameState", row: int, col: int, player: str) -> None:
    """Reveal fog within Manhattan distance ≤ 3; add 4 cardinal-axis distance-3
    tiles to the valid moves pool.  Trigger any Barbarians newly revealed.
    """
    revealed_extra: list = state.data.setdefault("revealed_extra", [])
    revealed_set   = {(p[0], p[1]) for p in revealed_extra}
    newly_revealed: list[tuple[int, int]] = []

    for r in range(state.height):
        for c in range(state.width):
            if abs(r - row) + abs(c - col) <= 3:
                if (r, c) not in revealed_set:
                    revealed_extra.append([r, c])
                    revealed_set.add((r, c))
                    newly_revealed.append((r, c))

    # Valid moves: only the 4 cardinal-axis tiles at exactly distance 3
    pool     = state.data["valid_moves"][player]
    pool_set = _pool_as_set(pool)
    for dr, dc in CARDINAL_DELTAS:
        nr, nc = row + dr * 3, col + dc * 3
        if 0 <= nr < state.height and 0 <= nc < state.width:
            t = state.tile(nr, nc)
            if t["owner"] is None and t["type"] != "mountain":
                key = (nr, nc)
                if key not in pool_set:
                    pool_set.add(key)
                    pool.append([nr, nc])

    # Barbarian reveal check for all newly visible tiles
    check_barbarian_visibility(state, newly_revealed)


# ---------------------------------------------------------------------------
# Cave
# ---------------------------------------------------------------------------

def apply_cave(state: "GameState", row: int, col: int, player: str) -> None:
    """Connect with a pending unconnected Cave, or register this one and add
    all remaining unclaimed non-inert Caves to the player's pool.
    Also adds cardinal neighbors to the pool (like Forest).
    """
    from game.rules import expand_pool_forest
    expand_pool_forest(state, row, col, player)

    unconnected: list = state.data["unconnected_caves"][player]

    if unconnected:
        # Connect the new Cave with the most-recently-claimed unconnected Cave
        partner = unconnected.pop()
        pr, pc  = partner[0], partner[1]

        state.tile(row, col)["special_state"]["inert"]        = True
        state.tile(row, col)["special_state"]["connected_to"] = [pr, pc]
        state.tile(pr, pc)["special_state"]["inert"]          = True
        state.tile(pr, pc)["special_state"]["connected_to"]   = [row, col]
        # Both tiles are already owned; no pool changes needed.
    else:
        # Register as pending and add all unclaimed non-inert Caves to pool
        state.data["unconnected_caves"][player].append([row, col])
        pool     = state.data["valid_moves"][player]
        pool_set = _pool_as_set(pool)
        for r in range(state.height):
            for c in range(state.width):
                t = state.tile(r, c)
                if (t["type"] == "cave"
                        and t["owner"] is None
                        and not t["special_state"].get("inert")):
                    key = (r, c)
                    if key not in pool_set:
                        pool_set.add(key)
                        pool.append([r, c])


# ---------------------------------------------------------------------------
# Wizard
# ---------------------------------------------------------------------------

def apply_wizard(state: "GameState", _row: int, _col: int, player: str) -> None:
    """Grant the Wizard one-time teleport ability to the claiming player."""
    state.data["wizard_held_by"] = player


def apply_wizard_teleport(state: "GameState", row: int, col: int) -> None:
    """Use the Wizard ability: claim any unclaimed non-Mountain tile.

    Consumes the ability and advances the turn.
    """
    from game.win import check_win

    player = state.data["turn"]
    tile   = state.data["board"][row][col]

    tile["owner"] = player
    state.data["scores"][player] += 1
    remove_from_pools(state, row, col)

    # Apply the tile's normal effect (it's now claimed via teleport)
    from game.rules import _apply_tile_effect
    _apply_tile_effect(state, row, col, player, tile["type"])

    state.data["wizard_held_by"] = None
    state.data["turn"] = "ai" if player == "human" else "human"
    check_win(state)


def validate_wizard_teleport(state: "GameState", row: int, col: int) -> tuple[bool, str]:
    if state.wizard_held_by != state.turn:
        return False, "Current player does not hold the Wizard ability"
    t = state.tile(row, col)
    if t["owner"] is not None:
        return False, "Tile is already claimed"
    if t["type"] == "mountain":
        return False, "Cannot teleport to a mountain"
    return True, "OK"


# ---------------------------------------------------------------------------
# Barbarian
# ---------------------------------------------------------------------------

def check_barbarian_visibility(
    state: "GameState",
    newly_visible: list[tuple[int, int]],
) -> None:
    """Trigger any untriggered Barbarians that appear in newly_visible."""
    for r, c in newly_visible:
        t = state.tile(r, c)
        if t["type"] == "barbarian" and not t["special_state"].get("triggered"):
            _trigger_barbarian(state, r, c)


def _trigger_barbarian(state: "GameState", barb_r: int, barb_c: int) -> None:
    """Sweep the Barbarian's row or column, unclaiming every non-Mountain tile.
    Replace the Barbarian tile with Forest afterwards and recompute pools.
    """
    tile      = state.tile(barb_r, barb_c)
    direction = tile["special_state"]["direction"]
    tile["special_state"]["triggered"] = True

    positions = (
        [(barb_r, c) for c in range(state.width)]
        if direction == "horizontal"
        else [(r, barb_c) for r in range(state.height)]
    )

    for r, c in positions:
        t = state.data["board"][r][c]
        if t["type"] == "mountain":
            continue  # passed through, unchanged
        if t["owner"] is not None:
            state.data["scores"][t["owner"]] -= 1
            t["owner"] = None
        # Non-mountain tiles in path are reset to claimable Forest
        if t["type"] == "barbarian":
            # The Barbarian tile itself becomes Forest
            state.data["board"][r][c] = {
                "type":          "forest",
                "owner":         None,
                "visible":       True,
                "special_state": {},
            }
        else:
            t["type"]   = "forest"
            t["visible"] = True   # Swept tiles are now revealed

    recompute_pools(state)


def recompute_pools(state: "GameState") -> None:
    """Rebuild both players' valid moves pools from scratch.

    Used after Barbarian sweeps (which can break connectivity) and at any
    point where a full pool refresh is needed.
    """
    new_pools: dict[str, list] = {"human": [], "ai": []}
    pool_sets: dict[str, set]  = {"human": set(), "ai": set()}

    for r in range(state.height):
        for c in range(state.width):
            tile        = state.tile(r, c)
            owner       = tile["owner"]
            tile_type   = tile["type"]

            if owner not in ("human", "ai"):
                continue

            if tile_type in ("forest", "domain"):
                for nr, nc in cardinal_neighbors(r, c, state.height, state.width):
                    nb = state.tile(nr, nc)
                    if nb["owner"] is None and nb["type"] != "mountain":
                        key = (nr, nc)
                        if key not in pool_sets[owner]:
                            pool_sets[owner].add(key)
                            new_pools[owner].append([nr, nc])

            elif tile_type == "tower":
                for dr, dc in CARDINAL_DELTAS:
                    nr, nc = r + dr * 3, c + dc * 3
                    if 0 <= nr < state.height and 0 <= nc < state.width:
                        nb = state.tile(nr, nc)
                        if nb["owner"] is None and nb["type"] != "mountain":
                            key = (nr, nc)
                            if key not in pool_sets[owner]:
                                pool_sets[owner].add(key)
                                new_pools[owner].append([nr, nc])

            elif tile_type == "cave":
                # All claimed caves expand to cardinal neighbors (like forest)
                for nr, nc in cardinal_neighbors(r, c, state.height, state.width):
                    nb = state.tile(nr, nc)
                    if nb["owner"] is None and nb["type"] != "mountain":
                        key = (nr, nc)
                        if key not in pool_sets[owner]:
                            pool_sets[owner].add(key)
                            new_pools[owner].append([nr, nc])
                # Non-inert caves also expose all unclaimed non-inert caves (tunnel mechanic)
                if not tile["special_state"].get("inert"):
                    for r2 in range(state.height):
                        for c2 in range(state.width):
                            t2 = state.tile(r2, c2)
                            if (t2["type"] == "cave"
                                    and t2["owner"] is None
                                    and not t2["special_state"].get("inert")):
                                key = (r2, c2)
                                if key not in pool_sets[owner]:
                                    pool_sets[owner].add(key)
                                    new_pools[owner].append([r2, c2])

    state.data["valid_moves"] = new_pools
