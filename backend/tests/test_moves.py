"""Tests for move validation, fog of war, and basic expansion rules."""

import pytest
from game.board import FOREST, DOMAIN, MOUNTAIN, BARBARIAN
from game.state import GameState
from game.rules import make_move, InvalidMoveError
from game.effects import recompute_valid_moves


def _minimal_state(extra_tiles=None):
    """Build a tiny 6×6 board state with controlled tile layout.

    We override the board after construction for precise placement.
    """
    state = GameState({
        "width": 6, "height": 6, "seed": 0,
        "difficulty": "easy", "domain_tiles_per_player": 1,
    })
    return state


# ---------------------------------------------------------------------------
# Basic valid-moves behaviour
# ---------------------------------------------------------------------------

class TestForestExpansion:
    def test_forest_adds_cardinal_neighbours(self):
        state = _minimal_state()
        # Pick the human's domain tile and check valid moves include all
        # cardinal neighbours that are unclaimed and non-mountain.
        human_pos = next(
            (r, c)
            for r in range(state.height)
            for c in range(state.width)
            if state.board[r][c]["owner"] == "human"
        )
        r, c = human_pos
        expected = set()
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = r + dr, c + dc
            if 0 <= nr < state.height and 0 <= nc < state.width:
                tile = state.board[nr][nc]
                if tile["type"] not in (MOUNTAIN, BARBARIAN) and tile["owner"] is None:
                    expected.add((nr, nc))
        vm = set(state.valid_moves["human"].keys())
        assert expected.issubset(vm)

    def test_claimed_tile_not_in_valid_moves(self):
        state = _minimal_state()
        # Human domain tile must not appear in valid moves
        for r in range(state.height):
            for c in range(state.width):
                if state.board[r][c]["owner"] is not None:
                    assert (r, c) not in state.valid_moves["human"]
                    assert (r, c) not in state.valid_moves["ai"]

    def test_mountain_not_in_valid_moves(self):
        state = _minimal_state()
        for r in range(state.height):
            for c in range(state.width):
                if state.board[r][c]["type"] == MOUNTAIN:
                    assert (r, c) not in state.valid_moves["human"]
                    assert (r, c) not in state.valid_moves["ai"]


class TestMoveValidation:
    def test_invalid_out_of_bounds(self):
        state = _minimal_state()
        with pytest.raises(InvalidMoveError):
            make_move(state, -1, 0)

    def test_invalid_already_owned(self):
        state = _minimal_state()
        # Find any ai-owned tile
        ai_pos = next(
            (r, c)
            for r in range(state.height)
            for c in range(state.width)
            if state.board[r][c]["owner"] == "ai"
        )
        # Force human turn to try to claim it
        with pytest.raises(InvalidMoveError):
            make_move(state, ai_pos[0], ai_pos[1])

    def test_invalid_not_in_pool(self):
        state = _minimal_state()
        # Find any unclaimed, non-mountain tile not in human's pool
        candidate = next(
            (r, c)
            for r in range(state.height)
            for c in range(state.width)
            if state.board[r][c]["owner"] is None
            and state.board[r][c]["type"] not in (MOUNTAIN, BARBARIAN)
            and (r, c) not in state.valid_moves["human"]
        )
        with pytest.raises(InvalidMoveError):
            make_move(state, candidate[0], candidate[1])

    def test_valid_move_accepted(self):
        state = _minimal_state()
        vm = list(state.valid_moves["human"].keys())
        assert vm, "Human should have at least one valid move"
        r, c = vm[0]
        make_move(state, r, c)  # should not raise
        assert state.board[r][c]["owner"] == "human"

    def test_turn_advances_after_move(self):
        state = _minimal_state()
        assert state.turn == "human"
        vm = list(state.valid_moves["human"].keys())
        make_move(state, vm[0][0], vm[0][1])
        assert state.turn == "ai"


class TestFogOfWar:
    def test_valid_move_tiles_visible(self):
        state = _minimal_state()
        for player in ("human", "ai"):
            for (r, c) in state.valid_moves[player]:
                assert state.board[r][c]["visible"] is True

    def test_fog_tiles_not_in_pool(self):
        state = _minimal_state()
        fogged = [
            (r, c)
            for r in range(state.height)
            for c in range(state.width)
            if not state.board[r][c]["visible"]
            and state.board[r][c]["owner"] is None
        ]
        all_vm = (
            set(state.valid_moves["human"]) | set(state.valid_moves["ai"])
        )
        for pos in fogged:
            assert pos not in all_vm

    def test_claimed_tile_reveals_neighbours(self):
        state = _minimal_state()
        vm = list(state.valid_moves["human"].keys())
        r, c = vm[0]
        make_move(state, r, c)
        # The newly claimed forest tile should have revealed its neighbours
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = r + dr, c + dc
            if state.in_bounds(nr, nc):
                tile = state.board[nr][nc]
                if tile["type"] not in (MOUNTAIN, BARBARIAN):
                    assert tile["visible"] is True


class TestScoring:
    def test_score_reflects_owned_tiles(self):
        state = _minimal_state()
        human_count = sum(
            1 for r in range(state.height)
            for c in range(state.width)
            if state.board[r][c]["owner"] == "human"
        )
        assert state.scores["human"] == human_count

    def test_score_increases_after_claim(self):
        state = _minimal_state()
        before = state.scores["human"]
        vm = list(state.valid_moves["human"].keys())
        make_move(state, vm[0][0], vm[0][1])
        assert state.scores["human"] == before + 1
