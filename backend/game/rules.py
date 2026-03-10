"""High-level move validation and application.

This module is the only entry point for mutating a GameState during normal
gameplay.  The minimax engine bypasses validation (it only generates legal
moves) and calls effects.apply_move() directly.
"""

from game.board import MOUNTAIN, BARBARIAN, CLAIMABLE
from game.effects import apply_move
from game.win import check_win


class InvalidMoveError(Exception):
    pass


def player_has_moves(state, player):
    """Return True if player has at least one valid move or an unused wizard."""
    has_normal = bool(state.valid_moves[player])
    has_wizard = (
        state.wizard_held_by == player
        and not state.wizard_used.get(player, False)
    )
    return has_normal or has_wizard


def pass_turn(state):
    """Skip the current player's turn when they have no valid moves.

    Advances to the opponent.  If the opponent also has no moves, force-ends
    the game by tile count (both players are stuck — no more progress possible).
    """
    if state.status != "in_progress":
        return

    state.turn = "ai" if state.turn == "human" else "human"

    # If the new current player is also stuck, the game cannot advance further.
    if not player_has_moves(state, state.turn):
        h = state.scores["human"]
        a = state.scores["ai"]
        if h > a:
            state.status = "human_wins"
        elif a > h:
            state.status = "ai_wins"
        else:
            state.status = "tie"


def get_valid_moves(state, player=None):
    """Return list of (r, c) that player (defaults to state.turn) can claim."""
    player = player or state.turn
    return list(state.valid_moves[player].keys())


def make_move(state, r, c, wizard=False):
    """Validate and apply the current player's move.

    wizard=True means the player is using their one-time wizard teleport
    instead of a normal move.

    Returns list of game events.
    Raises InvalidMoveError on illegal input.
    """
    player = state.turn

    _validate_move(state, r, c, player, wizard)

    events = apply_move(state, r, c, player, wizard=wizard)
    check_win(state)

    if state.status == "in_progress":
        state.turn = "ai" if player == "human" else "human"

    return events


def _validate_move(state, r, c, player, wizard):
    if not state.in_bounds(r, c):
        raise InvalidMoveError(f"Position ({r}, {c}) is out of bounds.")

    tile = state.board[r][c]

    if tile["owner"] is not None:
        raise InvalidMoveError(f"Tile ({r}, {c}) is already owned.")

    if tile["type"] in (MOUNTAIN, BARBARIAN):
        raise InvalidMoveError(f"Tile ({r}, {c}) is not claimable ({tile['type']}).")

    if wizard:
        if state.wizard_held_by != player:
            raise InvalidMoveError(f"{player} does not hold the wizard ability.")
        if state.wizard_used.get(player, False):
            raise InvalidMoveError("Wizard ability has already been used.")
    else:
        if (r, c) not in state.valid_moves[player]:
            raise InvalidMoveError(f"({r}, {c}) is not in {player}'s valid moves pool.")
