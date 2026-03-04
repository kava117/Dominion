"""Board evaluation heuristic for the minimax AI.

evaluate(state, ai_player) → float
Higher values are better for ai_player.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game.state import GameState

# ---------------------------------------------------------------------------
# Weights (tunable)
# ---------------------------------------------------------------------------
WEIGHT_TILE      = 10   # per-tile score lead
WEIGHT_MOBILITY  = 1    # per-move pool lead
WEIGHT_WIZARD    = 20   # holding the wizard ability
WEIGHT_CAVE_PAIR = 5    # per connected cave tile owned
WEIGHT_BARB_TILE = 3    # per owned tile in a Barbarian's sweep path (penalty)

# Bonus for having a high-value tile in the valid moves pool
POOL_SPECIAL_BONUS = {
    "wizard":    25,
    "tower":     15,
    "cave":      10,
    "plains":     8,
}

WIN_SCORE  =  1_000_000
LOSE_SCORE = -1_000_000


def evaluate(state: "GameState", ai_player: str) -> float:
    """Return a numeric score for state from ai_player's perspective."""
    human_player = "human" if ai_player == "ai" else "ai"

    # Terminal states
    if state.status != "in_progress":
        if state.status == f"{ai_player}_wins":
            return WIN_SCORE
        if state.status == f"{human_player}_wins":
            return LOSE_SCORE
        return 0  # tie

    ai_score = state.scores[ai_player]
    hu_score = state.scores[human_player]

    ai_vm = state.data["valid_moves"].get(ai_player, [])
    hu_vm = state.data["valid_moves"].get(human_player, [])

    score = 0.0

    # 1. Tile count lead
    score += (ai_score - hu_score) * WEIGHT_TILE

    # 2. Mobility (pool size) lead
    score += (len(ai_vm) - len(hu_vm)) * WEIGHT_MOBILITY

    # 3. Special tiles in AI's valid moves pool
    for pos in ai_vm:
        t = state.tile(pos[0], pos[1])
        score += POOL_SPECIAL_BONUS.get(t["type"], 0)

    # 4. Wizard ability
    if state.wizard_held_by == ai_player:
        score += WEIGHT_WIZARD
    elif state.wizard_held_by == human_player:
        score -= WEIGHT_WIZARD

    # 5. Connected (inert) caves owned by AI
    for r in range(state.height):
        for c in range(state.width):
            t = state.tile(r, c)
            if t["type"] == "cave" and t["owner"] == ai_player and t["special_state"].get("inert"):
                score += WEIGHT_CAVE_PAIR

    # 6. Barbarian threat — penalise AI tiles in the sweep path of untriggered Barbarians
    for r in range(state.height):
        for c in range(state.width):
            t = state.tile(r, c)
            if t["type"] == "barbarian" and not t["special_state"].get("triggered"):
                direction = t["special_state"]["direction"]
                if direction == "horizontal":
                    ai_exposed = sum(
                        1 for sc in range(state.width)
                        if state.tile(r, sc)["owner"] == ai_player
                    )
                else:
                    ai_exposed = sum(
                        1 for sr in range(state.height)
                        if state.tile(sr, c)["owner"] == ai_player
                    )
                score -= ai_exposed * WEIGHT_BARB_TILE

    return score
