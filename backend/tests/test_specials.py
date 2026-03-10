"""Tests for special tile behaviour: Plains, Tower, Cave, Wizard, Barbarian."""

import pytest
from game.board import (
    FOREST, PLAINS, TOWER, CAVE, WIZARD, BARBARIAN, MOUNTAIN, DOMAIN
)
from game.state import GameState
from game.effects import apply_move, add_tile_valid_moves, recompute_valid_moves
from game.rules import make_move, InvalidMoveError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _blank_board(width, height, fill=FOREST):
    return [[{"type": fill, "owner": None, "visible": False, "inert": False}
             for _ in range(width)] for _ in range(height)]


def _state_with_board(board, width=None, height=None):
    """Create a GameState shell with a manually set board."""
    w = width or len(board[0])
    h = height or len(board)
    state = GameState.__new__(GameState)
    state.config = {}
    state.width = w
    state.height = h
    state.seed = 0
    state.difficulty = "medium"
    state.domain_tiles_per_player = 1
    state.board = board
    state.turn = "human"
    state.status = "in_progress"
    state.wizard_held_by = None
    state.wizard_used = {"human": False, "ai": False}
    state.valid_moves = {"human": {}, "ai": {}}
    state.scores = {"human": 0, "ai": 0}
    return state


# ---------------------------------------------------------------------------
# Plains
# ---------------------------------------------------------------------------

class TestPlains:
    def test_plains_adds_tiles_within_distance_2(self):
        board = _blank_board(7, 7)
        # Place a claimed plains at (3, 3)
        board[3][3] = {"type": PLAINS, "owner": "human", "visible": True, "inert": False}
        state = _state_with_board(board)
        state.scores["human"] = 1
        add_tile_valid_moves(state, 3, 3, "human")

        vm = set(state.valid_moves["human"].keys())
        # All tiles at distance <= 2 that are unclaimed non-mountain should be in vm
        for r in range(7):
            for c in range(7):
                dist = abs(r - 3) + abs(c - 3)
                tile = board[r][c]
                if dist <= 2 and tile["owner"] is None and tile["type"] != MOUNTAIN:
                    assert (r, c) in vm, f"({r},{c}) dist={dist} should be valid"

    def test_plains_reveals_fog_within_2(self):
        board = _blank_board(7, 7)
        board[3][3] = {"type": PLAINS, "owner": "human", "visible": True, "inert": False}
        state = _state_with_board(board)
        state.scores["human"] = 1
        add_tile_valid_moves(state, 3, 3, "human")

        for r in range(7):
            for c in range(7):
                if abs(r - 3) + abs(c - 3) <= 2:
                    assert state.board[r][c]["visible"] is True

    def test_plains_does_not_add_beyond_distance_2(self):
        board = _blank_board(7, 7)
        board[3][3] = {"type": PLAINS, "owner": "human", "visible": True, "inert": False}
        state = _state_with_board(board)
        add_tile_valid_moves(state, 3, 3, "human")

        vm = set(state.valid_moves["human"].keys())
        for r in range(7):
            for c in range(7):
                dist = abs(r - 3) + abs(c - 3)
                if dist > 2:
                    assert (r, c) not in vm


# ---------------------------------------------------------------------------
# Tower
# ---------------------------------------------------------------------------

class TestTower:
    def test_tower_adds_exactly_distance_3(self):
        board = _blank_board(9, 9)
        board[4][4] = {"type": TOWER, "owner": "human", "visible": True, "inert": False}
        state = _state_with_board(board)
        state.scores["human"] = 1
        add_tile_valid_moves(state, 4, 4, "human")

        vm = set(state.valid_moves["human"].keys())
        for r in range(9):
            for c in range(9):
                dist = abs(r - 4) + abs(c - 4)
                tile = board[r][c]
                if dist == 3 and tile["owner"] is None and tile["type"] != MOUNTAIN:
                    assert (r, c) in vm, f"({r},{c}) dist=3 should be valid"

    def test_tower_does_not_add_distance_1_or_2(self):
        board = _blank_board(9, 9)
        board[4][4] = {"type": TOWER, "owner": "human", "visible": True, "inert": False}
        state = _state_with_board(board)
        add_tile_valid_moves(state, 4, 4, "human")

        vm = set(state.valid_moves["human"].keys())
        for r in range(9):
            for c in range(9):
                dist = abs(r - 4) + abs(c - 4)
                if 0 < dist < 3:
                    assert (r, c) not in vm, f"({r},{c}) dist={dist} should NOT be valid"

    def test_tower_reveals_within_3(self):
        board = _blank_board(9, 9)
        board[4][4] = {"type": TOWER, "owner": "human", "visible": True, "inert": False}
        state = _state_with_board(board)
        add_tile_valid_moves(state, 4, 4, "human")

        for r in range(9):
            for c in range(9):
                if abs(r - 4) + abs(c - 4) <= 3:
                    assert state.board[r][c]["visible"] is True


# ---------------------------------------------------------------------------
# Cave
# ---------------------------------------------------------------------------

class TestCave:
    def _two_cave_state(self):
        """5×5 board with human-owned cave at (0,0) and unclaimed cave at (4,4)."""
        board = _blank_board(5, 5)
        board[0][0] = {"type": CAVE, "owner": "human", "visible": True, "inert": False}
        board[4][4] = {"type": CAVE, "owner": None, "visible": False, "inert": False}
        state = _state_with_board(board)
        state.scores["human"] = 1
        add_tile_valid_moves(state, 0, 0, "human")
        return state

    def test_cave_adds_other_caves(self):
        state = self._two_cave_state()
        assert (4, 4) in state.valid_moves["human"]

    def test_cave_adds_via_cave_source(self):
        state = self._two_cave_state()
        entry = state.valid_moves["human"][(4, 4)]
        assert (0, 0) in entry["cave_sources"]
        assert not entry["non_cave"]

    def test_cave_connection_on_claim(self):
        state = self._two_cave_state()
        # Human claims (4,4) via cave link
        apply_move(state, 4, 4, "human")
        assert state.board[4][4]["inert"] is True
        assert state.board[0][0]["inert"] is True
        assert state.board[4][4]["owner"] == "human"

    def test_cave_connection_removed_from_pool(self):
        state = self._two_cave_state()
        apply_move(state, 4, 4, "human")
        # Neither cave should remain in valid moves
        assert (4, 4) not in state.valid_moves["human"]
        assert (4, 4) not in state.valid_moves["ai"]

    def test_no_cave_connection_when_non_cave_source_exists(self):
        """If a cave is reachable by both a cave AND a forest, no connection forms."""
        board = _blank_board(5, 5)
        # Cave A at (0,0) owned by human
        board[0][0] = {"type": CAVE, "owner": "human", "visible": True, "inert": False}
        # Cave B at (2,2) — unclaimed; also adjacent to a forest at (1,2)
        board[2][2] = {"type": CAVE, "owner": None, "visible": False, "inert": False}
        # Forest at (1,2) owned by human (will add (2,2) as non-cave)
        board[1][2] = {"type": FOREST, "owner": "human", "visible": True, "inert": False}
        state = _state_with_board(board)
        state.scores["human"] = 2
        add_tile_valid_moves(state, 0, 0, "human")
        add_tile_valid_moves(state, 1, 2, "human")

        entry = state.valid_moves["human"].get((2, 2))
        assert entry is not None
        assert entry["non_cave"] is True  # forest source exists

        # Claim (2,2): cave connection should NOT form
        apply_move(state, 2, 2, "human")
        assert state.board[2][2]["inert"] is False
        assert state.board[0][0]["inert"] is False

    def test_inert_cave_does_not_add_moves(self):
        board = _blank_board(5, 5)
        board[0][0] = {"type": CAVE, "owner": "human", "visible": True, "inert": True}
        board[4][4] = {"type": CAVE, "owner": None, "visible": False, "inert": False}
        state = _state_with_board(board)
        state.scores["human"] = 1
        add_tile_valid_moves(state, 0, 0, "human")
        assert (4, 4) not in state.valid_moves["human"]


# ---------------------------------------------------------------------------
# Wizard
# ---------------------------------------------------------------------------

class TestWizard:
    def _wizard_state(self):
        """Human owns a forest; there's a wizard tile they can claim."""
        board = _blank_board(6, 6)
        board[0][0] = {"type": FOREST, "owner": "human", "visible": True, "inert": False}
        board[5][5] = {"type": WIZARD, "owner": None, "visible": True, "inert": False}
        state = _state_with_board(board)
        state.scores["human"] = 1
        add_tile_valid_moves(state, 0, 0, "human")
        return state

    def test_wizard_acquired_on_claim(self):
        state = self._wizard_state()
        # Wizard at (5,5) must be reachable somehow; let's place it adjacent
        board = _blank_board(4, 4)
        board[0][0] = {"type": FOREST, "owner": "human", "visible": True, "inert": False}
        board[0][1] = {"type": WIZARD, "owner": None, "visible": True, "inert": False}
        state = _state_with_board(board)
        state.scores["human"] = 1
        add_tile_valid_moves(state, 0, 0, "human")
        assert (0, 1) in state.valid_moves["human"]

        apply_move(state, 0, 1, "human")
        assert state.wizard_held_by == "human"

    def test_wizard_teleport_claims_any_unclaimed(self):
        board = _blank_board(6, 6)
        board[0][0] = {"type": FOREST, "owner": "human", "visible": True, "inert": False}
        board[5][5] = {"type": FOREST, "owner": None, "visible": False, "inert": False}
        state = _state_with_board(board)
        state.scores["human"] = 1
        state.wizard_held_by = "human"

        apply_move(state, 5, 5, "human", wizard=True)
        assert state.board[5][5]["owner"] == "human"
        assert state.wizard_used["human"] is True

    def test_wizard_cannot_teleport_to_mountain(self):
        board = _blank_board(4, 4)
        board[0][0] = {"type": FOREST, "owner": "human", "visible": True, "inert": False}
        board[3][3] = {"type": MOUNTAIN, "owner": None, "visible": True, "inert": False}
        state = _state_with_board(board)
        state.wizard_held_by = "human"
        state.turn = "human"

        with pytest.raises(InvalidMoveError):
            make_move(state, 3, 3, wizard=True)

    def test_wizard_can_only_be_used_once(self):
        board = _blank_board(5, 5)
        board[0][0] = {"type": FOREST, "owner": "human", "visible": True, "inert": False}
        board[4][4] = {"type": FOREST, "owner": None, "visible": False, "inert": False}
        board[4][3] = {"type": FOREST, "owner": None, "visible": False, "inert": False}
        state = _state_with_board(board)
        state.scores["human"] = 1
        state.wizard_held_by = "human"
        state.wizard_used["human"] = True
        state.turn = "human"

        with pytest.raises(InvalidMoveError):
            make_move(state, 4, 4, wizard=True)

    def test_non_holder_cannot_use_wizard(self):
        board = _blank_board(4, 4)
        board[0][0] = {"type": FOREST, "owner": "human", "visible": True, "inert": False}
        state = _state_with_board(board)
        state.wizard_held_by = "ai"
        state.turn = "human"

        with pytest.raises(InvalidMoveError):
            make_move(state, 2, 2, wizard=True)


# ---------------------------------------------------------------------------
# Barbarian
# ---------------------------------------------------------------------------

class TestBarbarian:

    # ------------------------------------------------------------------
    # Reveal triggers
    # ------------------------------------------------------------------

    def test_barbarian_triggers_when_adjacent_to_claimed_tile(self):
        """Claiming any tile reveals its cardinal neighbours; a barbarian there fires."""
        board = _blank_board(6, 6)
        # Human owns forest at (2,2); barbarian is adjacent at (2,3)
        board[2][2] = {"type": FOREST, "owner": "human", "visible": True, "inert": False}
        board[2][1] = {"type": FOREST, "owner": None, "visible": True, "inert": False}
        board[2][3] = {"type": BARBARIAN, "owner": None, "visible": False, "inert": False}
        state = _state_with_board(board, width=6, height=6)
        state.scores["human"] = 1
        add_tile_valid_moves(state, 2, 2, "human")

        # Claim (2,1) — its right neighbour (2,2) is already owned, left (2,0) and
        # (1,1)/(3,1) are forest.  We actually want to claim a tile that exposes (2,3).
        # Direct path: claim forest at (2,2) is already owned; claim (2,1) reveals (2,2)
        # already visible.  Use apply_move on (2,1) which reveals (2,0),(1,1),(3,1),(2,2)
        # — none are barbarians.  Better: make (2,2) the tile being claimed this turn.
        # Reset: human doesn't own (2,2) yet; owns domain at (2,0).
        board2 = _blank_board(6, 6)
        board2[2][0] = {"type": DOMAIN, "owner": "human", "visible": True, "inert": False}
        board2[2][1] = {"type": BARBARIAN, "owner": None, "visible": False, "inert": False}
        state2 = _state_with_board(board2, width=6, height=6)
        state2.scores["human"] = 1
        add_tile_valid_moves(state2, 2, 0, "human")

        # (2,1) is a barbarian so it won't be in the valid-moves pool.
        # Claim (1,0) which is adjacent to (2,0). Revealing (1,0)'s neighbours
        # won't hit (2,1). Instead claim a forest that is 1 step from the barbarian.
        # Simplest: place a forest at (2,2) that human can reach, revealing (2,1).
        board3 = _blank_board(6, 6)
        board3[2][2] = {"type": FOREST, "owner": "human", "visible": True, "inert": False}
        board3[2][3] = {"type": BARBARIAN, "owner": None, "visible": False, "inert": False}
        board3[2][1] = {"type": FOREST, "owner": None, "visible": True, "inert": False}
        state3 = _state_with_board(board3, width=6, height=6)
        state3.scores["human"] = 1
        add_tile_valid_moves(state3, 2, 2, "human")

        # (2,1) is in the valid moves pool; claiming it reveals (2,0),(1,1),(3,1),(2,2)
        # — no barbarian. Claim the forest tile *at* (2,1) instead, whose right neighbour
        # is (2,2) already owned, and whose east side has no barbarian.
        # Cleanest test: claim (2,1), which has (2,2) as neighbour — already visible.
        # The reveal of (2,3) happens when we claim (2,2)... but (2,2) is already owned.
        # Let's just claim a new tile adjacent to the barbarian directly.
        board4 = _blank_board(6, 6)
        board4[2][1] = {"type": FOREST, "owner": "human", "visible": True, "inert": False}
        board4[2][2] = {"type": FOREST, "owner": None, "visible": True, "inert": False}
        board4[2][3] = {"type": BARBARIAN, "owner": None, "visible": False, "inert": False}
        state4 = _state_with_board(board4, width=6, height=6)
        state4.scores["human"] = 1
        add_tile_valid_moves(state4, 2, 1, "human")

        # Claim (2,2): _reveal_neighbors reveals (2,3) → barbarian fires
        apply_move(state4, 2, 2, "human")
        assert state4.board[2][3]["type"] == FOREST, \
            "Barbarian adjacent to newly claimed tile should have triggered"

    def test_barbarian_triggers_when_revealed_by_tower(self):
        """Claiming a tower tile reveals dist-3 area; barbarian there should trigger."""
        board = _blank_board(9, 9)
        board[4][3] = {"type": FOREST, "owner": "human", "visible": True, "inert": False}
        board[4][4] = {"type": TOWER, "owner": None, "visible": False, "inert": False}
        # Barbarian at (4,7): manhattan distance 3 from (4,4)
        board[4][7] = {"type": BARBARIAN, "owner": None, "visible": False, "inert": False}
        state = _state_with_board(board, width=9, height=9)
        state.scores["human"] = 1
        add_tile_valid_moves(state, 4, 3, "human")

        apply_move(state, 4, 4, "human")

        assert state.board[4][7]["type"] == FOREST

    def test_barbarian_triggers_when_revealed_by_plains(self):
        """Claiming a plains tile reveals dist-2 area; barbarian there should trigger."""
        board = _blank_board(7, 7)
        board[3][2] = {"type": FOREST, "owner": "human", "visible": True, "inert": False}
        board[3][3] = {"type": PLAINS, "owner": None, "visible": False, "inert": False}
        # Barbarian at (3,5): manhattan distance 2 from (3,3)
        board[3][5] = {"type": BARBARIAN, "owner": None, "visible": False, "inert": False}
        state = _state_with_board(board, width=7, height=7)
        state.scores["human"] = 1
        add_tile_valid_moves(state, 3, 2, "human")

        apply_move(state, 3, 3, "human")

        assert state.board[3][5]["type"] == FOREST

    # ------------------------------------------------------------------
    # Direction selection
    # ------------------------------------------------------------------

    def test_direction_longest_path_left(self):
        """Barbarian near the right edge should charge left (longer path)."""
        from game.effects import _barbarian_direction
        # 10 wide, 6 tall. Barbarian at col 8: left=8, right=1 → left wins.
        state = _state_with_board(_blank_board(10, 6), width=10, height=6)
        assert _barbarian_direction(state, 3, 8) == "left"

    def test_direction_longest_path_right(self):
        """Barbarian near the left edge should charge right (longer path)."""
        from game.effects import _barbarian_direction
        # 10 wide, 6 tall. Barbarian at col 1: left=1, right=8 → right wins.
        state = _state_with_board(_blank_board(10, 6), width=10, height=6)
        assert _barbarian_direction(state, 3, 1) == "right"

    def test_direction_longest_path_down(self):
        """Barbarian near the top edge should charge down (longer path)."""
        from game.effects import _barbarian_direction
        # 6 wide, 10 tall. Barbarian at row 1: up=1, down=8 → down wins.
        state = _state_with_board(_blank_board(6, 10), width=6, height=10)
        assert _barbarian_direction(state, 1, 3) == "down"

    def test_direction_longest_path_up(self):
        """Barbarian near the bottom edge should charge up (longer path)."""
        from game.effects import _barbarian_direction
        # 6 wide, 10 tall. Barbarian at row 8: up=8, down=1 → up wins.
        state = _state_with_board(_blank_board(6, 10), width=6, height=10)
        assert _barbarian_direction(state, 8, 3) == "up"

    # ------------------------------------------------------------------
    # Charge path (only from barbarian to the chosen edge)
    # ------------------------------------------------------------------

    def test_charge_left_unclaims_only_tiles_left_of_barbarian(self):
        """Barbarian charges left: only tiles from col 0 to barbarian column are hit."""
        w, h = 10, 6
        board = _blank_board(w, h)
        # Barbarian at (2, 8): left=8, right=1 → charges left (cols 0–8)
        board[2][8] = {"type": BARBARIAN, "owner": None, "visible": True, "inert": False}
        board[2][3] = {"type": FOREST, "owner": "human", "visible": True, "inert": False}
        board[2][9] = {"type": FOREST, "owner": "ai",   "visible": True, "inert": False}
        state = _state_with_board(board, width=w, height=h)
        state.scores = {"human": 1, "ai": 1}

        from game.effects import _trigger_barbarian
        _trigger_barbarian(state, 2, 8)

        assert state.board[2][3]["owner"] is None, "tile left of barbarian should be unclaimed"
        assert state.board[2][9]["owner"] == "ai", "tile right of barbarian should be untouched"

    def test_charge_right_unclaims_only_tiles_right_of_barbarian(self):
        """Barbarian charges right: only tiles from barbarian column to right edge are hit."""
        w, h = 10, 6
        board = _blank_board(w, h)
        # Barbarian at (2, 1): left=1, right=8 → charges right (cols 1–9)
        board[2][1] = {"type": BARBARIAN, "owner": None, "visible": True, "inert": False}
        board[2][0] = {"type": FOREST, "owner": "human", "visible": True, "inert": False}
        board[2][5] = {"type": FOREST, "owner": "ai",   "visible": True, "inert": False}
        state = _state_with_board(board, width=w, height=h)
        state.scores = {"human": 1, "ai": 1}

        from game.effects import _trigger_barbarian
        _trigger_barbarian(state, 2, 1)

        assert state.board[2][0]["owner"] == "human", "tile left of barbarian should be untouched"
        assert state.board[2][5]["owner"] is None, "tile right of barbarian should be unclaimed"

    def test_charge_does_not_reveal_hidden_tiles(self):
        """The barbarian charge must not set visible=True on any tile in its path."""
        w, h = 8, 4
        board = _blank_board(w, h)
        # Barbarian at (1, 6): left=6 wins → charges left
        board[1][6] = {"type": BARBARIAN, "owner": None, "visible": True, "inert": False}
        # Hidden unowned tile in the charge path
        board[1][2] = {"type": FOREST, "owner": None, "visible": False, "inert": False}
        state = _state_with_board(board, width=w, height=h)

        from game.effects import _trigger_barbarian
        _trigger_barbarian(state, 1, 6)

        assert state.board[1][2]["visible"] is False, \
            "Barbarian charge must not reveal hidden tiles"

    def test_hidden_barbarian_not_triggered_by_charge(self):
        """A barbarian that is still hidden when another fires must not trigger."""
        w, h = 10, 4
        board = _blank_board(w, h)
        # Barbarian A at (1,8): left=8 → charges left
        board[1][8] = {"type": BARBARIAN, "owner": None, "visible": True,  "inert": False}
        # Barbarian B at (1,3): hidden — in the charge path but must NOT trigger
        board[1][3] = {"type": BARBARIAN, "owner": None, "visible": False, "inert": False}
        state = _state_with_board(board, width=w, height=h)

        from game.effects import _trigger_barbarian
        _trigger_barbarian(state, 1, 8)

        # B is still a BARBARIAN (not converted to Forest)
        assert state.board[1][3]["type"] == BARBARIAN, \
            "Hidden barbarian in charge path must not trigger"

    # ------------------------------------------------------------------
    # Misc
    # ------------------------------------------------------------------

    def test_barbarian_converts_to_forest_after_trigger(self):
        board = _blank_board(6, 4)
        # Barbarian at (2,2): left=2, right=3 → charges right
        board[2][2] = {"type": BARBARIAN, "owner": None, "visible": True, "inert": False}
        state = _state_with_board(board, width=6, height=4)

        from game.effects import _trigger_barbarian
        _trigger_barbarian(state, 2, 2)

        assert state.board[2][2]["type"] == FOREST

    def test_barbarian_mountains_unaffected(self):
        w, h = 8, 4
        board = _blank_board(w, h)
        # Barbarian at (1,5): left=5 wins → charges left (cols 0–5)
        board[1][5] = {"type": BARBARIAN, "owner": None, "visible": True, "inert": False}
        board[1][2] = {"type": MOUNTAIN, "owner": None, "visible": True, "inert": False}
        board[1][3] = {"type": FOREST, "owner": "human", "visible": True, "inert": False}
        state = _state_with_board(board, width=w, height=h)
        state.scores["human"] = 1

        from game.effects import _trigger_barbarian
        _trigger_barbarian(state, 1, 5)

        assert state.board[1][2]["type"] == MOUNTAIN
        assert state.board[1][3]["owner"] is None
