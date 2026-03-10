"""Board evaluation heuristic for the minimax engine."""

from game.board import WIZARD, TOWER, CAVE, PLAINS


# Score weights
W_TILE_DELTA = 10
W_MOVE_DELTA = 3
W_SPECIAL = {WIZARD: 15, TOWER: 8, CAVE: 6, PLAINS: 4}
W_WIZARD_HELD = 20


def evaluate(state):
    """Return a numeric score from the AI's perspective (higher = better for AI)."""
    if state.status == "ai_wins":
        return 1_000_000
    if state.status == "human_wins":
        return -1_000_000
    if state.status == "tie":
        return 0

    score = 0

    # Tile count delta
    score += (state.scores["ai"] - state.scores["human"]) * W_TILE_DELTA

    # Valid-moves delta (territory potential)
    ai_moves = len(state.valid_moves["ai"])
    human_moves = len(state.valid_moves["human"])
    score += (ai_moves - human_moves) * W_MOVE_DELTA

    # Special tile proximity — bonus if a special is in AI's pool, penalty if in human's
    for r in range(state.height):
        for c in range(state.width):
            tile = state.board[r][c]
            bonus = W_SPECIAL.get(tile["type"], 0)
            if bonus and tile["owner"] is None and tile["visible"]:
                if (r, c) in state.valid_moves["ai"]:
                    score += bonus
                if (r, c) in state.valid_moves["human"]:
                    score -= bonus

    # Wizard-held bonus
    if state.wizard_held_by == "ai" and not state.wizard_used.get("ai", False):
        score += W_WIZARD_HELD
    elif state.wizard_held_by == "human" and not state.wizard_used.get("human", False):
        score -= W_WIZARD_HELD

    return score
