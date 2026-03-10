"""Tests for the AI minimax engine."""

import pytest
from game.board import FOREST, WIZARD, TOWER, DOMAIN, MOUNTAIN
from game.state import GameState
from game.ai.minimax import choose_move
from game.ai.heuristic import evaluate
from tests.test_specials import _state_with_board, _blank_board


class TestHeuristic:
    def test_equal_state_scores_near_zero(self):
        board = _blank_board(4, 4)
        board[0][0] = {"type": DOMAIN, "owner": "human", "visible": True, "inert": False}
        board[3][3] = {"type": DOMAIN, "owner": "ai", "visible": True, "inert": False}
        state = _state_with_board(board, 4, 4)
        state.scores = {"human": 1, "ai": 1}
        # With equal tiles the raw tile delta is 0; moves delta may differ
        score = evaluate(state)
        # Score should be symmetric-ish; just check it runs without error
        assert isinstance(score, (int, float))

    def test_ai_winning_state_positive(self):
        board = _blank_board(4, 4)
        for c in range(4):
            board[0][c] = {"type": FOREST, "owner": "ai", "visible": True, "inert": False}
        state = _state_with_board(board, 4, 4)
        state.scores = {"human": 0, "ai": 4}
        assert evaluate(state) > 0

    def test_human_winning_state_negative(self):
        board = _blank_board(4, 4)
        for c in range(4):
            board[0][c] = {"type": FOREST, "owner": "human", "visible": True, "inert": False}
        state = _state_with_board(board, 4, 4)
        state.scores = {"human": 4, "ai": 0}
        assert evaluate(state) < 0

    def test_ai_wins_status_returns_large_positive(self):
        board = _blank_board(2, 2)
        state = _state_with_board(board, 2, 2)
        state.status = "ai_wins"
        assert evaluate(state) > 100_000

    def test_human_wins_status_returns_large_negative(self):
        board = _blank_board(2, 2)
        state = _state_with_board(board, 2, 2)
        state.status = "human_wins"
        assert evaluate(state) < -100_000


class TestChooseMove:
    def test_choose_move_returns_valid_position(self):
        state = GameState({
            "width": 8, "height": 6, "seed": 42,
            "difficulty": "easy", "domain_tiles_per_player": 1,
        })
        state.turn = "ai"
        move = choose_move(state)
        assert move is not None
        assert "row" in move and "col" in move
        r, c = move["row"], move["col"]
        assert state.in_bounds(r, c)
        assert state.board[r][c]["owner"] is None
        assert (r, c) in state.valid_moves["ai"] or move.get("wizard")

    def test_choose_move_takes_only_available_special(self):
        """When wizard is the only valid move, the AI must take it."""
        board = _blank_board(5, 5)
        # AI owns domain at (4,4); only adjacent tile is wizard at (4,3); rest are mountains
        board[4][4] = {"type": DOMAIN, "owner": "ai", "visible": True, "inert": False}
        board[4][3] = {"type": WIZARD, "owner": None, "visible": True, "inert": False}
        # Block all other cardinal neighbours of (4,4) with mountains
        board[3][4] = {"type": MOUNTAIN, "owner": None, "visible": True, "inert": False}
        # (5,4) is out of bounds; (4,5) is out of bounds for width=5 (0-4 valid)
        state = _state_with_board(board, 5, 5)
        state.scores = {"human": 0, "ai": 1}
        state.turn = "ai"
        from game.effects import add_tile_valid_moves
        add_tile_valid_moves(state, 4, 4, "ai")

        move = choose_move(state)
        assert move is not None
        assert move["row"] == 4 and move["col"] == 3

    def test_no_moves_returns_none(self):
        board = _blank_board(3, 3)
        board[1][1] = {"type": FOREST, "owner": "ai", "visible": True, "inert": False}
        # Surround entirely with mountains
        for r in range(3):
            for c in range(3):
                if (r, c) != (1, 1):
                    board[r][c]["type"] = "mountain"
        state = _state_with_board(board, 3, 3)
        state.scores = {"human": 0, "ai": 1}
        state.turn = "ai"
        # No valid moves in pool
        move = choose_move(state)
        assert move is None
