"""Win-condition evaluation."""

from game.board import MOUNTAIN


def count_claimable(state):
    """Total non-mountain tiles (the denominator for win conditions)."""
    count = 0
    for r in range(state.height):
        for c in range(state.width):
            if state.board[r][c]["type"] != MOUNTAIN:
                count += 1
    return count


def check_win(state):
    """Evaluate win conditions and update state.status if the game is over.

    Two conditions (spec §8):
      Standard:  all claimable tiles have been claimed.
      Dominant:  one player holds > 50% of claimable tiles AND the opponent
                 has no valid moves.
    """
    if state.status != "in_progress":
        return

    total = count_claimable(state)
    human = state.scores["human"]
    ai = state.scores["ai"]
    claimed = human + ai

    # Standard end
    if claimed >= total:
        if human > ai:
            state.status = "human_wins"
        elif ai > human:
            state.status = "ai_wins"
        else:
            state.status = "tie"
        return

    # Dominant end
    half = total / 2
    for player, opponent in (("human", "ai"), ("ai", "human")):
        if state.scores[player] > half:
            opp_has_moves = bool(state.valid_moves[opponent])
            opp_has_wizard = (
                state.wizard_held_by == opponent
                and not state.wizard_used.get(opponent, False)
            )
            if not opp_has_moves and not opp_has_wizard:
                state.status = f"{player}_wins"
                return
