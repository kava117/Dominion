"""Minimax with alpha-beta pruning for the AI opponent."""

from game.board import MOUNTAIN, BARBARIAN, TILE_PRIORITY
from game.effects import apply_move
from game.win import check_win
from game.ai.heuristic import evaluate

DEPTH_FOR_DIFFICULTY = {"easy": 2, "medium": 4, "hard": 6}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def choose_move(state, force=False):
    """Return the best move for the AI as {"row": r, "col": c, "wizard": bool}.

    Returns None if the AI has no moves (shouldn't happen in normal play).
    If force=True, use depth 1 for an instant response (timeout fallback).
    """
    depth = 1 if force else DEPTH_FOR_DIFFICULTY.get(state.difficulty, 4)
    _, move = _minimax(state, depth, float("-inf"), float("inf"), maximizing=True)
    return move


# ---------------------------------------------------------------------------
# Move generation
# ---------------------------------------------------------------------------

def _get_moves(state, player):
    """Return all candidate moves for player as list of (r, c, wizard_flag)."""
    moves = []

    # Normal valid moves
    for (r, c) in state.valid_moves[player]:
        moves.append((r, c, False))

    # Wizard teleport moves
    if (state.wizard_held_by == player
            and not state.wizard_used.get(player, False)):
        for r in range(state.height):
            for c in range(state.width):
                tile = state.board[r][c]
                if tile["type"] not in (MOUNTAIN, BARBARIAN) and tile["owner"] is None:
                    moves.append((r, c, True))

    return moves


def _move_sort_key(state, r, c, wizard):
    """Ordering key: special tiles first, then by how much the move expands moves."""
    if wizard:
        # Wizard moves are very high priority
        return (10, 0)
    tile = state.board[r][c]
    priority = TILE_PRIORITY.get(tile["type"], 0)
    return (priority, 0)


def _order_moves(state, moves, player):
    return sorted(moves, key=lambda m: _move_sort_key(state, m[0], m[1], m[2]), reverse=True)


# ---------------------------------------------------------------------------
# Minimax
# ---------------------------------------------------------------------------

def _minimax(state, depth, alpha, beta, maximizing):
    if depth == 0 or state.status != "in_progress":
        return evaluate(state), None

    player = "ai" if maximizing else "human"
    moves = _get_moves(state, player)

    if not moves:
        # No moves available; evaluate as-is (turn effectively skipped)
        return evaluate(state), None

    moves = _order_moves(state, moves, player)

    best_move = None

    if maximizing:
        best_val = float("-inf")
        for r, c, wiz in moves:
            child = state.clone()
            apply_move(child, r, c, player, wizard=wiz)
            check_win(child)
            if child.status == "in_progress":
                child.turn = "human"
            val, _ = _minimax(child, depth - 1, alpha, beta, False)
            if val > best_val:
                best_val = val
                best_move = {"row": r, "col": c, "wizard": wiz}
            alpha = max(alpha, val)
            if beta <= alpha:
                break
        return best_val, best_move
    else:
        best_val = float("inf")
        for r, c, wiz in moves:
            child = state.clone()
            apply_move(child, r, c, player, wizard=wiz)
            check_win(child)
            if child.status == "in_progress":
                child.turn = "ai"
            val, _ = _minimax(child, depth - 1, alpha, beta, True)
            if val < best_val:
                best_val = val
                best_move = {"row": r, "col": c, "wizard": wiz}
            beta = min(beta, val)
            if beta <= alpha:
                break
        return best_val, best_move
