"""Tests for win condition evaluation."""

import pytest
from game.board import FOREST, MOUNTAIN, DOMAIN
from game.win import check_win, count_claimable
from game.state import GameState
from game.effects import apply_move


def _state_with_board(board, width=None, height=None):
    from tests.test_specials import _state_with_board as _swb
    return _swb(board, width, height)


def _blank_board(w, h, fill=FOREST):
    return [[{"type": fill, "owner": None, "visible": True, "inert": False}
             for _ in range(w)] for _ in range(h)]


# ---------------------------------------------------------------------------

class TestCountClaimable:
    def test_all_forest(self):
        board = _blank_board(4, 4)
        state = _state_with_board(board, 4, 4)
        assert count_claimable(state) == 16

    def test_excludes_mountains(self):
        board = _blank_board(4, 4)
        board[0][0]["type"] = MOUNTAIN
        board[1][1]["type"] = MOUNTAIN
        state = _state_with_board(board, 4, 4)
        assert count_claimable(state) == 14


class TestStandardEnd:
    def test_all_tiles_claimed_human_wins(self):
        board = _blank_board(2, 2)
        board[0][0]["owner"] = "human"
        board[0][1]["owner"] = "human"
        board[1][0]["owner"] = "human"
        board[1][1]["owner"] = "ai"
        state = _state_with_board(board, 2, 2)
        state.scores = {"human": 3, "ai": 1}
        check_win(state)
        assert state.status == "human_wins"

    def test_all_tiles_claimed_ai_wins(self):
        board = _blank_board(2, 2)
        board[0][0]["owner"] = "ai"
        board[0][1]["owner"] = "ai"
        board[1][0]["owner"] = "ai"
        board[1][1]["owner"] = "human"
        state = _state_with_board(board, 2, 2)
        state.scores = {"human": 1, "ai": 3}
        check_win(state)
        assert state.status == "ai_wins"

    def test_all_tiles_claimed_tie(self):
        board = _blank_board(2, 2)
        board[0][0]["owner"] = "human"
        board[0][1]["owner"] = "human"
        board[1][0]["owner"] = "ai"
        board[1][1]["owner"] = "ai"
        state = _state_with_board(board, 2, 2)
        state.scores = {"human": 2, "ai": 2}
        check_win(state)
        assert state.status == "tie"


class TestDominantEnd:
    def test_dominant_player_wins_when_opponent_has_no_moves(self):
        board = _blank_board(4, 2)
        # Human owns 5 of 8 tiles (> 50%), AI has no valid moves
        board[0][0]["owner"] = "human"
        board[0][1]["owner"] = "human"
        board[0][2]["owner"] = "human"
        board[0][3]["owner"] = "human"
        board[1][0]["owner"] = "human"
        state = _state_with_board(board, 4, 2)
        state.scores = {"human": 5, "ai": 0}
        state.valid_moves["ai"] = {}  # no moves
        check_win(state)
        assert state.status == "human_wins"

    def test_not_dominant_if_opponent_has_moves(self):
        board = _blank_board(4, 2)
        board[0][0]["owner"] = "human"
        board[0][1]["owner"] = "human"
        board[0][2]["owner"] = "human"
        board[0][3]["owner"] = "human"
        board[1][0]["owner"] = "human"
        state = _state_with_board(board, 4, 2)
        state.scores = {"human": 5, "ai": 0}
        state.valid_moves["ai"] = {(1, 1): {"non_cave": True, "cave_sources": []}}
        check_win(state)
        assert state.status == "in_progress"

    def test_exactly_half_is_not_dominant(self):
        board = _blank_board(4, 2)
        # 4 of 8 = exactly 50%; dominant requires > 50%
        board[0][0]["owner"] = "human"
        board[0][1]["owner"] = "human"
        board[0][2]["owner"] = "human"
        board[0][3]["owner"] = "human"
        state = _state_with_board(board, 4, 2)
        state.scores = {"human": 4, "ai": 0}
        state.valid_moves["ai"] = {}
        check_win(state)
        assert state.status == "in_progress"

    def test_dominant_not_triggered_when_game_already_over(self):
        board = _blank_board(2, 2)
        state = _state_with_board(board, 2, 2)
        state.status = "human_wins"
        state.scores = {"human": 0, "ai": 0}
        check_win(state)  # should be a no-op
        assert state.status == "human_wins"

    def test_dominant_with_wizard_held_blocks_win(self):
        """If opponent has no normal moves but holds an unused wizard, game continues."""
        board = _blank_board(4, 2)
        board[0][0]["owner"] = "human"
        board[0][1]["owner"] = "human"
        board[0][2]["owner"] = "human"
        board[0][3]["owner"] = "human"
        board[1][0]["owner"] = "human"
        state = _state_with_board(board, 4, 2)
        state.scores = {"human": 5, "ai": 0}
        state.valid_moves["ai"] = {}
        state.wizard_held_by = "ai"
        state.wizard_used["ai"] = False
        check_win(state)
        assert state.status == "in_progress"
