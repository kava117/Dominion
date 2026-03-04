"""Minimax with alpha-beta pruning for Domain Expansion AI.

Public API:
    get_best_move(state, timeout_seconds) -> move_dict | None
    apply_ai_move(state, move)             -> None  (mutates state)
    get_all_moves(state)                   -> list[move_dict]

Move dict shapes:
    {"type": "normal",  "row": r, "col": c, "tile_type": str}
    {"type": "wizard",  "row": r, "col": c}
    {"type": "plains",  "row": r, "col": c, "first": [r,c]|None, "second": [r,c]|None}
"""
from __future__ import annotations

import copy
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game.state import GameState

from game.ai.heuristic import evaluate
from game.rules import apply_move, cardinal_neighbors, CARDINAL_DELTAS
from game.effects import (
    apply_plains_first_pick,
    apply_plains_second_pick,
    apply_wizard_teleport,
)

# ---------------------------------------------------------------------------
# Difficulty → search depth
# ---------------------------------------------------------------------------
DIFFICULTY_DEPTH = {"easy": 2, "medium": 4, "hard": 6}

# ---------------------------------------------------------------------------
# Move ordering priority (higher = searched first → better pruning)
# ---------------------------------------------------------------------------
_MOVE_PRIORITY = {
    "wizard_use": 7,   # using the wizard teleport ability
    "wizard":     6,   # claiming the wizard tile
    "tower":      5,
    "cave":       4,
    "plains":     3,
    "forest":     1,
    "domain":     1,
    "barbarian":  0,   # can't normally claim active barbarians
}


# ===========================================================================
# Public API
# ===========================================================================

def get_best_move(state: "GameState", timeout_seconds: float = 10.0):
    """Return the best move dict for the current (AI) player, or None."""
    depth     = DIFFICULTY_DEPTH.get(state.difficulty, 4)
    ai_player = state.turn
    moves     = get_all_moves(state)

    if not moves:
        return None

    deadline  = time.time() + timeout_seconds
    best_val  = float("-inf")
    best_move = moves[0]

    for move in moves:
        if time.time() > deadline:
            break
        sim = _simulate(state, move)
        val, _ = _minimax(sim, depth - 1, float("-inf"), float("inf"), ai_player, deadline)
        if val > best_val:
            best_val  = val
            best_move = move

    return best_move


def apply_ai_move(state: "GameState", move: dict) -> None:
    """Apply a move dict (from get_best_move) to the *real* game state."""
    if move["type"] == "wizard":
        apply_wizard_teleport(state, move["row"], move["col"])

    elif move["type"] in ("normal",):
        apply_move(state, move["row"], move["col"])

    elif move["type"] == "plains":
        apply_move(state, move["row"], move["col"])
        if move.get("first") is not None and state.data.get("phase") == "plains_first_pick":
            apply_plains_first_pick(state, move["first"][0], move["first"][1])
            if move.get("second") is not None and state.data.get("phase") == "plains_second_pick":
                apply_plains_second_pick(state, move["second"][0], move["second"][1])


def get_all_moves(state: "GameState") -> list[dict]:
    """Return all legal moves for the current player, ordered for good pruning."""
    player = state.turn
    moves: list[dict] = []

    # Wizard teleport (if held)
    if state.wizard_held_by == player:
        for r in range(state.height):
            for c in range(state.width):
                t = state.tile(r, c)
                if t["owner"] is None and t["type"] != "mountain":
                    moves.append({"type": "wizard", "row": r, "col": c})

    # Normal moves from valid pool
    for pos in state.data["valid_moves"].get(player, []):
        r, c = pos[0], pos[1]
        t    = state.tile(r, c)
        if t["type"] == "plains":
            moves.extend(_enumerate_plains(state, r, c))
        else:
            moves.append({
                "type":      "normal",
                "row":       r,
                "col":       c,
                "tile_type": t["type"],
            })

    _order_moves(moves, state)
    return moves


# ===========================================================================
# Core minimax
# ===========================================================================

def _minimax(
    state:        "GameState",
    depth:        int,
    alpha:        float,
    beta:         float,
    ai_player:    str,
    deadline:     float,
) -> tuple[float, dict | None]:
    if time.time() > deadline or depth == 0 or state.status != "in_progress":
        return evaluate(state, ai_player), None

    moves = get_all_moves(state)
    if not moves:
        return evaluate(state, ai_player), None

    is_maximizing = (state.turn == ai_player)
    best_move     = None

    if is_maximizing:
        best_val = float("-inf")
        for move in moves:
            sim      = _simulate(state, move)
            val, _   = _minimax(sim, depth - 1, alpha, beta, ai_player, deadline)
            if val > best_val:
                best_val  = val
                best_move = move
            alpha = max(alpha, val)
            if beta <= alpha:
                break
        return best_val, best_move

    else:
        best_val = float("inf")
        for move in moves:
            sim     = _simulate(state, move)
            val, _  = _minimax(sim, depth - 1, alpha, beta, ai_player, deadline)
            if val < best_val:
                best_val  = val
                best_move = move
            beta = min(beta, val)
            if beta <= alpha:
                break
        return best_val, best_move


def minimax_no_pruning(
    state:     "GameState",
    depth:     int,
    ai_player: str,
) -> tuple[float, dict | None]:
    """Plain minimax without alpha-beta — used for correctness tests only."""
    if depth == 0 or state.status != "in_progress":
        return evaluate(state, ai_player), None

    moves = get_all_moves(state)
    if not moves:
        return evaluate(state, ai_player), None

    is_maximizing = (state.turn == ai_player)
    best_val      = float("-inf") if is_maximizing else float("inf")
    best_move     = None

    for move in moves:
        sim    = _simulate(state, move)
        val, _ = minimax_no_pruning(sim, depth - 1, ai_player)
        if is_maximizing and val > best_val:
            best_val, best_move = val, move
        elif not is_maximizing and val < best_val:
            best_val, best_move = val, move

    return best_val, best_move


# ===========================================================================
# Move generation helpers
# ===========================================================================

def _enumerate_plains(state: "GameState", pr: int, pc: int) -> list[dict]:
    """Enumerate all (plains_pos, first_pick, second_pick) compound moves."""
    sim1 = _clone(state)
    apply_move(sim1, pr, pc)

    if sim1.data.get("phase") != "plains_first_pick":
        # Plains ended immediately (no picks available)
        return [{"type": "plains", "row": pr, "col": pc, "first": None, "second": None,
                 "tile_type": "plains"}]

    first_picks = sim1.data["phase_data"].get("valid_picks", [])
    if not first_picks:
        return [{"type": "plains", "row": pr, "col": pc, "first": None, "second": None,
                 "tile_type": "plains"}]

    compounds = []
    for fp in first_picks:
        sim2 = _clone(sim1)
        apply_plains_first_pick(sim2, fp[0], fp[1])

        if sim2.data.get("phase") == "plains_second_pick":
            second_picks = sim2.data["phase_data"].get("valid_picks", [])
            if not second_picks:
                compounds.append({
                    "type": "plains", "row": pr, "col": pc,
                    "first": fp, "second": None, "tile_type": "plains",
                })
            else:
                for sp in second_picks:
                    compounds.append({
                        "type": "plains", "row": pr, "col": pc,
                        "first": fp, "second": sp, "tile_type": "plains",
                    })
        else:
            compounds.append({
                "type": "plains", "row": pr, "col": pc,
                "first": fp, "second": None, "tile_type": "plains",
            })

    return compounds


def _order_moves(moves: list[dict], state: "GameState") -> None:
    """Sort moves in-place: special tiles first, then by pool expansion."""
    def _key(move):
        if move["type"] == "wizard":
            return (_MOVE_PRIORITY["wizard_use"], 0)
        tile_type = move.get("tile_type", "forest")
        sp  = _MOVE_PRIORITY.get(tile_type, 1)
        exp = (_expansion_potential(state, move["row"], move["col"])
               if move["type"] in ("normal", "plains") else 0)
        return (sp, exp)

    moves.sort(key=_key, reverse=True)


def _expansion_potential(state: "GameState", row: int, col: int) -> int:
    """Count unclaimed non-mountain cardinal neighbours (proxy for pool growth)."""
    return sum(
        1 for nr, nc in cardinal_neighbors(row, col, state.height, state.width)
        if state.tile(nr, nc)["owner"] is None
        and state.tile(nr, nc)["type"] != "mountain"
    )


# ===========================================================================
# Simulation helpers
# ===========================================================================

def _clone(state: "GameState") -> "GameState":
    from game.state import GameState
    return GameState(copy.deepcopy(state.data))


def _simulate(state: "GameState", move: dict) -> "GameState":
    """Return a new state after applying move (original is not mutated)."""
    sim = _clone(state)

    if move["type"] == "wizard":
        apply_wizard_teleport(sim, move["row"], move["col"])

    elif move["type"] == "normal":
        apply_move(sim, move["row"], move["col"])

    elif move["type"] == "plains":
        apply_move(sim, move["row"], move["col"])
        if move.get("first") is not None and sim.data.get("phase") == "plains_first_pick":
            apply_plains_first_pick(sim, move["first"][0], move["first"][1])
            if move.get("second") is not None and sim.data.get("phase") == "plains_second_pick":
                apply_plains_second_pick(sim, move["second"][0], move["second"][1])

    return sim
