"""Win condition checks and turn management.

Called after every move (including Plains sub-picks) to determine whether
the game has ended, and to skip a player's turn when they have no moves.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game.state import GameState


def check_win(state: "GameState") -> None:
    """Evaluate win conditions and update state.status + state.turn in-place.

    Must be called after every move, AFTER the turn has already advanced to
    the next player.

    Win conditions (spec §8):
    1. Standard end  — all claimable tiles are claimed → compare scores.
    2. Dominant end  — one player owns > 50 % of claimable tiles AND the
                       opponent has 0 valid moves.

    After checking wins, if the game is still in progress but the active
    player has 0 valid moves, their turn is skipped (spec §4 clarification).
    If BOTH players have 0 valid moves the game ends as a standard end even
    if some tiles are unclaimed (nobody can make progress).
    """
    if state.status != "in_progress":
        return

    _resolve_status(state)

    # Turn-skip: if game is still going but active player has no moves, pass.
    if state.status == "in_progress":
        _maybe_skip_turn(state)


def _resolve_status(state: "GameState") -> None:
    scores          = state.scores
    claimable_total = state.claimable_total
    claimed_total   = scores["human"] + scores["ai"]

    human_vm = state.data["valid_moves"].get("human", [])
    ai_vm    = state.data["valid_moves"].get("ai", [])
    human_has_moves = len(human_vm) > 0
    ai_has_moves    = len(ai_vm) > 0

    # --- Standard end: all claimable tiles taken, or nobody can move ---
    if claimed_total >= claimable_total or (not human_has_moves and not ai_has_moves):
        _set_winner(state)
        return

    # --- Dominant end: one player > 50 % AND opponent has 0 valid moves ---
    threshold = claimable_total / 2
    if scores["human"] > threshold and not ai_has_moves:
        state.data["status"] = "human_wins"
        return
    if scores["ai"] > threshold and not human_has_moves:
        state.data["status"] = "ai_wins"
        return


def _set_winner(state: "GameState") -> None:
    h = state.scores["human"]
    a = state.scores["ai"]
    if h > a:
        state.data["status"] = "human_wins"
    elif a > h:
        state.data["status"] = "ai_wins"
    else:
        state.data["status"] = "tie"


def _maybe_skip_turn(state: "GameState") -> None:
    """If the current player has no valid moves, pass to the opponent."""
    current  = state.data["turn"]
    opponent = "ai" if current == "human" else "human"
    if not state.data["valid_moves"].get(current):
        state.data["turn"] = opponent
