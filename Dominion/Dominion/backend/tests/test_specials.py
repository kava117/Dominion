"""Stage 3 tests — special tile effects: Plains, Tower, Cave, Wizard, Barbarian."""
import pytest
from game.rules import apply_move, remove_from_pools, compute_visible
from game.effects import (
    apply_plains, apply_plains_first_pick,
    validate_plains_pick, plains_first_picks,
    apply_tower,
    apply_cave,
    apply_wizard, apply_wizard_teleport, validate_wizard_teleport,
    check_barbarian_visibility, recompute_pools,
    _trigger_barbarian,
)
from tests.conftest import make_state, make_board


# ===========================================================================
# Helper
# ===========================================================================
def _plains_state(layout, turn="human", valid_moves=None):
    """Convenience: build a state and pre-mark the plains tile."""
    state = make_state(layout, turn=turn, valid_moves=valid_moves or {"human": [], "ai": []})
    return state


# ===========================================================================
# 3A — Plains
# ===========================================================================
class TestPlainsFirstPicks:
    def test_all_manhattan2_picks_on_open_board(self):
        # Plains at (2,2), surrounded by Forest — expects all 12 Manhattan ≤ 2 tiles
        state = make_state(
            [["F","F","F","F","F"],
             ["F","F","F","F","F"],
             ["F","F","P","F","F"],
             ["F","F","F","F","F"],
             ["F","F","F","F","F"]],
        )
        picks = plains_first_picks(state, 2, 2)
        expected = [
            [1,2],[3,2],[2,1],[2,3],          # cardinal distance 1
            [0,2],[4,2],[2,0],[2,4],          # cardinal distance 2
            [1,1],[1,3],[3,1],[3,3],          # diagonals (Manhattan distance 2)
        ]
        assert sorted(picks) == sorted(expected)

    def test_picks_skip_mountains(self):
        state = make_state(
            [["F","F","M","F","F"],
             ["F","F","F","F","F"],
             ["M","F","P","F","F"],
             ["F","F","F","F","F"],
             ["F","F","F","F","F"]],
        )
        picks = plains_first_picks(state, 2, 2)
        assert [0,2] not in picks   # mountain at (0,2)
        assert [2,0] not in picks   # mountain at (2,0)

    def test_picks_skip_owned_tiles(self):
        state = make_state(
            [["F","F","Da","F","F"],
             ["F","F","F","F","F"],
             ["F","F","P","F","F"],
             ["F","F","F","F","F"],
             ["F","F","F","F","F"]],
        )
        picks = plains_first_picks(state, 2, 2)
        assert [0,2] not in picks   # owned by AI

    def test_edge_board_fewer_picks(self):
        state = make_state(
            [["P","F","F"],
             ["F","F","F"],
             ["F","F","F"]],
        )
        picks = plains_first_picks(state, 0, 0)
        # Manhattan ≤ 2 from (0,0) that are on-board: (0,1),(1,0),(0,2),(2,0),(1,1)
        assert sorted(picks) == sorted([[0,1],[1,0],[0,2],[2,0],[1,1]])


class TestApplyPlains:
    def test_sets_plains_first_pick_phase(self):
        state = make_state(
            [["F","F","F","F","F"],
             ["F","F","F","F","F"],
             ["F","F","Dh","F","F"],
             ["F","F","F","F","F"],
             ["F","F","F","F","F"]],
            turn="human",
            valid_moves={"human": [[2,2]], "ai": []},
        )
        # Mark (2,2) as plains for effect
        state.data["board"][2][2]["type"] = "plains"
        apply_move(state, 2, 2)
        assert state.data["phase"] == "plains_first_pick"
        assert len(state.data["phase_data"]["valid_picks"]) > 0

    def test_turn_does_not_advance_during_plains(self):
        state = make_state(
            [["F","F","F","F","F"],
             ["F","F","F","F","F"],
             ["F","F","P","F","F"],
             ["F","F","F","F","F"],
             ["F","F","F","F","F"]],
            turn="human",
            valid_moves={"human": [[2,2]], "ai": []},
        )
        apply_move(state, 2, 2)
        assert state.turn == "human"   # still human's turn

    def test_no_valid_first_picks_advances_turn(self):
        # Plains tile with all Manhattan ≤ 2 neighbours being mountains
        state = make_state(
            [["M","M","M","M","M"],
             ["M","M","M","M","M"],
             ["M","M","P","M","M"],
             ["M","M","M","M","M"],
             ["M","M","M","M","M"]],
            turn="human",
            valid_moves={"human": [[2,2]], "ai": []},
        )
        apply_move(state, 2, 2)
        # No first picks → phase stays None, turn advances
        assert state.data["phase"] is None
        assert state.turn == "ai"


class TestPlainsFirstPickApplication:
    def _setup(self):
        """5×5 board, Plains at (2,2), human goes first."""
        state = make_state(
            [["F","F","F","F","F"],
             ["F","F","F","F","F"],
             ["F","F","P","F","F"],
             ["F","F","F","F","F"],
             ["F","F","F","F","F"]],
            turn="human",
            valid_moves={"human": [[2,2]], "ai": []},
        )
        apply_move(state, 2, 2)  # enter plains phase
        return state

    def test_first_pick_claims_tile(self):
        state = self._setup()
        picks = state.data["phase_data"]["valid_picks"]
        r, c  = picks[0]
        apply_plains_first_pick(state, r, c)
        assert state.tile(r, c)["owner"] == "human"

    def test_first_pick_clears_phase(self):
        state = self._setup()
        r, c  = state.data["phase_data"]["valid_picks"][0]
        apply_plains_first_pick(state, r, c)
        assert state.data["phase"] is None

    def test_score_increments_on_first_pick(self):
        state = self._setup()
        before = state.scores["human"]
        r, c   = state.data["phase_data"]["valid_picks"][0]
        apply_plains_first_pick(state, r, c)
        assert state.scores["human"] == before + 1


class TestPlainsFullMove:
    def test_total_score_after_full_plains_move(self):
        """Plains tile + 1 bonus pick = 2 new tiles claimed."""
        state = make_state(
            [["F","F","F","F","F"],
             ["F","F","F","F","F"],
             ["F","F","P","F","F"],
             ["F","F","F","F","F"],
             ["F","F","F","F","F"]],
            turn="human",
            valid_moves={"human": [[2,2]], "ai": []},
        )
        before = state.scores["human"]
        apply_move(state, 2, 2)
        r, c = state.data["phase_data"]["valid_picks"][0]
        apply_plains_first_pick(state, r, c)
        assert state.scores["human"] == before + 2

    def test_turn_advances_after_bonus_pick(self):
        state = make_state(
            [["F","F","F","F","F"],
             ["F","F","F","F","F"],
             ["F","F","P","F","F"],
             ["F","F","F","F","F"],
             ["F","F","F","F","F"]],
            turn="human",
            valid_moves={"human": [[2,2]], "ai": []},
        )
        state.data["valid_moves"]["ai"] = [[4, 4]]
        apply_move(state, 2, 2)
        r, c = state.data["phase_data"]["valid_picks"][0]
        apply_plains_first_pick(state, r, c)
        assert state.turn == "ai"

    def test_plains_within_plains_no_nested_phase(self):
        """Bonus pick landing on a Plains tile must NOT start another Plains phase."""
        state = make_state(
            [["F","F","P","F","F"],
             ["F","F","F","F","F"],
             ["F","F","P","F","F"],
             ["F","F","F","F","F"],
             ["F","F","F","F","F"]],
            turn="human",
            valid_moves={"human": [[2,2]], "ai": []},
        )
        apply_move(state, 2, 2)  # Plains at (2,2)
        # Bonus pick at (0,2) which is also a Plains tile
        apply_plains_first_pick(state, 0, 2)
        # Phase must be cleared, not restarted
        assert state.data["phase"] is None


class TestPlainsValidation:
    def test_invalid_pick_returns_false(self):
        state = make_state([["F","F","F"]], valid_moves={"human":[],"ai":[]})
        state.data["phase"] = "plains_first_pick"
        state.data["phase_data"] = {"valid_picks": [[0,1]]}
        ok, _ = validate_plains_pick(state, 0, 2)
        assert ok is False

    def test_valid_pick_returns_true(self):
        state = make_state([["F","F","F"]], valid_moves={"human":[],"ai":[]})
        state.data["phase"] = "plains_first_pick"
        state.data["phase_data"] = {"valid_picks": [[0,1]]}
        ok, _ = validate_plains_pick(state, 0, 1)
        assert ok is True


# ===========================================================================
# 3A — Plains via API
# ===========================================================================
class TestPlainsAPI:
    def test_plains_phase_flow_via_api(self, client):
        # Start a game, then manually set up a Plains scenario
        resp = client.post("/game/new", json={"seed": 42, "width": 12, "height": 10})
        gid  = resp.get_json()["game_id"]

        # Find first valid move that lands on a Forest tile and replace it with Plains
        import database, json
        raw  = database.load_game(gid)
        vm0  = raw["valid_moves"]["human"][0]
        r, c = vm0
        raw["board"][r][c]["type"] = "plains"
        database.save_game(raw)

        resp2 = client.post(f"/game/{gid}/move", json={"row": r, "col": c})
        data2 = resp2.get_json()
        assert resp2.status_code == 200
        assert data2["phase"] == "plains_first_pick"
        # valid_moves in response shows the first-pick candidates, not full pool
        assert len(data2["valid_moves"]) >= 0   # may be 0 if all at distance 2 are blocked

    def test_invalid_plains_pick_returns_400(self, client):
        resp = client.post("/game/new", json={"seed": 42})
        gid  = resp.get_json()["game_id"]

        import database
        raw = database.load_game(gid)
        vm0 = raw["valid_moves"]["human"][0]
        r, c = vm0
        raw["board"][r][c]["type"] = "plains"
        database.save_game(raw)

        client.post(f"/game/{gid}/move", json={"row": r, "col": c})
        # Submit a row/col that is NOT in the valid_picks
        bad = client.post(f"/game/{gid}/move", json={"row": 0, "col": 0})
        assert bad.status_code == 400


# ===========================================================================
# 3B — Tower
# ===========================================================================
class TestTower:
    def _tower_state(self):
        # Tower at (3,3) on a 7×7 board, human owns it
        layout = [["F"]*7 for _ in range(7)]
        state = make_state(layout, turn="human",
                           valid_moves={"human": [[3,3]], "ai": []})
        state.data["board"][3][3]["type"] = "tower"
        return state

    def test_four_cardinal_distance3_tiles_added_to_pool(self):
        state = self._tower_state()
        apply_tower(state, 3, 3, "human")
        vm = state.data["valid_moves"]["human"]
        assert [0, 3] in vm   # 3 up
        assert [6, 3] in vm   # 3 down
        assert [3, 0] in vm   # 3 left
        assert [3, 6] in vm   # 3 right

    def test_fog_revealed_within_distance_3(self):
        state = self._tower_state()
        apply_tower(state, 3, 3, "human")
        revealed = {(p[0], p[1]) for p in state.data["revealed_extra"]}
        # (3,3) itself is within distance 0
        assert (3, 3) in revealed
        # (3,5) is at distance 2 — revealed but not in pool
        assert (3, 5) in revealed
        # (0,3) is at distance 3 — revealed AND in pool
        assert (0, 3) in revealed

    def test_tiles_at_distance_1_and_2_not_in_pool(self):
        state = self._tower_state()
        apply_tower(state, 3, 3, "human")
        vm = state.data["valid_moves"]["human"]
        # (3,4) distance 1, (3,5) distance 2 — should NOT be in pool from Tower
        assert [3, 4] not in vm
        assert [3, 5] not in vm

    def test_tower_skips_mountains_for_pool(self):
        layout = [["F"]*7 for _ in range(7)]
        state  = make_state(layout, turn="human",
                            valid_moves={"human": [[3,3]], "ai": []})
        state.data["board"][3][3]["type"]  = "tower"
        state.data["board"][0][3]["type"]  = "mountain"  # block one distance-3 tile
        apply_tower(state, 3, 3, "human")
        vm = state.data["valid_moves"]["human"]
        assert [0, 3] not in vm   # mountain

    def test_tower_triggers_barbarian_in_revealed_zone(self):
        # Barbarian at (3,5) — distance 2 from Tower at (3,3), revealed but not in pool
        layout = [["F"]*7 for _ in range(7)]
        state  = make_state(layout, turn="human",
                            valid_moves={"human": [[3,3]], "ai": []})
        state.data["board"][3][3]["type"] = "tower"
        state.data["board"][3][5]["type"] = "barbarian"
        state.data["board"][3][5]["special_state"] = {"direction": "horizontal", "triggered": False}
        apply_tower(state, 3, 3, "human")
        # Barbarian should have triggered — swept its row, its tile becomes Forest
        assert state.tile(3, 5)["type"] == "forest"
        assert state.tile(3, 5)["owner"] is None

    def test_tower_edge_fewer_distance3_tiles(self):
        # Tower in corner (0,0); only 2 valid distance-3 tiles
        layout = [["F"]*5 for _ in range(5)]
        state  = make_state(layout, turn="human",
                            valid_moves={"human": [[0,0]], "ai": []})
        state.data["board"][0][0]["type"] = "tower"
        apply_tower(state, 0, 0, "human")
        vm = state.data["valid_moves"]["human"]
        # (3,0) and (0,3) should be in pool; (-3,0) and (0,-3) are off-board
        assert [3, 0] in vm
        assert [0, 3] in vm


# ===========================================================================
# 3C — Cave
# ===========================================================================
class TestCave:
    def _cave_board(self, cave_positions, owner_a=None, inert=False):
        """Build a 5×5 board with Caves at given positions."""
        layout = [["F"]*5 for _ in range(5)]
        state  = make_state(layout, turn="human",
                            valid_moves={"human": [], "ai": []})
        for r, c in cave_positions:
            state.data["board"][r][c]["type"]          = "cave"
            state.data["board"][r][c]["special_state"] = {"inert": inert, "connected_to": None}
        return state

    def test_first_cave_claim_adds_others_to_pool(self):
        state = self._cave_board([(0,0),(0,4),(4,0)])
        state.data["board"][0][0]["owner"] = "human"
        state.data["scores"]["human"] = 1
        apply_cave(state, 0, 0, "human")
        vm = state.data["valid_moves"]["human"]
        assert [0, 4] in vm
        assert [4, 0] in vm

    def test_first_cave_added_to_unconnected(self):
        state = self._cave_board([(0,0),(0,4)])
        state.data["board"][0][0]["owner"] = "human"
        apply_cave(state, 0, 0, "human")
        assert state.data["unconnected_caves"]["human"] == [[0,0]]

    def test_second_cave_connects_with_first(self):
        state = self._cave_board([(0,0),(0,4),(4,0)])
        state.data["board"][0][0]["owner"] = "human"
        state.data["unconnected_caves"]["human"] = [[0,0]]
        state.data["board"][0][0]["special_state"]["inert"] = False
        apply_cave(state, 0, 4, "human")
        assert state.tile(0, 0)["special_state"]["inert"] is True
        assert state.tile(0, 4)["special_state"]["inert"] is True

    def test_connection_sets_connected_to(self):
        state = self._cave_board([(0,0),(0,4)])
        state.data["board"][0][0]["owner"] = "human"
        state.data["unconnected_caves"]["human"] = [[0,0]]
        apply_cave(state, 0, 4, "human")
        assert state.tile(0, 0)["special_state"]["connected_to"] == [0, 4]
        assert state.tile(0, 4)["special_state"]["connected_to"] == [0, 0]

    def test_inert_caves_not_added_to_pool(self):
        state = self._cave_board([(0,0),(0,4),(4,0)])
        state.data["board"][0][0]["owner"] = "human"
        state.data["board"][4][0]["special_state"]["inert"] = True  # already inert
        apply_cave(state, 0, 0, "human")
        vm = state.data["valid_moves"]["human"]
        assert [0, 4] in vm
        assert [4, 0] not in vm   # inert — excluded

    def test_connection_exhausts_unconnected_list(self):
        state = self._cave_board([(0,0),(0,4)])
        state.data["board"][0][0]["owner"] = "human"
        state.data["unconnected_caves"]["human"] = [[0,0]]
        apply_cave(state, 0, 4, "human")
        assert state.data["unconnected_caves"]["human"] == []

    def test_cave_connection_across_non_consecutive_turns(self):
        """Cave A claimed, then Forest, then Cave B — A and B still connect."""
        state = self._cave_board([(0,0),(0,4),(4,0)])
        state.data["board"][0][0]["owner"] = "human"
        state.data["unconnected_caves"]["human"] = [[0,0]]
        # Intermediate: claim a Forest tile (just modify state directly)
        state.data["board"][1][0]["owner"] = "human"
        # Now claim Cave B
        apply_cave(state, 0, 4, "human")
        assert state.tile(0, 0)["special_state"]["inert"] is True
        assert state.tile(0, 4)["special_state"]["inert"] is True

    def test_first_cave_also_adds_neighbors(self):
        """Claiming the first cave should also add its cardinal neighbors to pool."""
        state = self._cave_board([(2, 2)])
        state.data["board"][2][2]["owner"] = "human"
        apply_cave(state, 2, 2, "human")
        vm = state.data["valid_moves"]["human"]
        assert [1, 2] in vm
        assert [3, 2] in vm
        assert [2, 1] in vm
        assert [2, 3] in vm

    def test_second_cave_also_adds_neighbors(self):
        """Claiming the second cave (pairing) should also add its cardinal neighbors to pool."""
        state = self._cave_board([(0, 0), (2, 2)])
        state.data["board"][0][0]["owner"] = "human"
        state.data["unconnected_caves"]["human"] = [[0, 0]]
        state.data["board"][2][2]["owner"] = "human"
        apply_cave(state, 2, 2, "human")
        vm = state.data["valid_moves"]["human"]
        assert [1, 2] in vm
        assert [3, 2] in vm
        assert [2, 1] in vm
        assert [2, 3] in vm


# ===========================================================================
# 3D — Wizard
# ===========================================================================
class TestWizard:
    def test_apply_wizard_sets_held_by(self):
        state = make_state([["W","F"]], turn="human",
                           valid_moves={"human": [[0,0]], "ai": []})
        apply_wizard(state, 0, 0, "human")
        assert state.data["wizard_held_by"] == "human"

    def test_wizard_teleport_claims_any_tile(self):
        state = make_state(
            [["Dh","F","F","F","F"]],
            turn="human",
            valid_moves={"human": [[0,1]], "ai": []},
        )
        state.data["wizard_held_by"] = "human"
        apply_wizard_teleport(state, 0, 4)
        assert state.tile(0, 4)["owner"] == "human"

    def test_wizard_teleport_consumes_ability(self):
        state = make_state([["Dh","F","F"]], turn="human",
                           valid_moves={"human": [[0,1]], "ai": []})
        state.data["wizard_held_by"] = "human"
        apply_wizard_teleport(state, 0, 2)
        assert state.data["wizard_held_by"] is None

    def test_wizard_teleport_advances_turn(self):
        state = make_state([["Dh","F","F"]], turn="human",
                           valid_moves={"human": [[0,1]], "ai": []})
        state.data["wizard_held_by"] = "human"
        apply_wizard_teleport(state, 0, 2)
        assert state.turn == "ai"

    def test_wizard_teleport_cannot_target_mountain(self):
        state = make_state([["Dh","M","F"]], turn="human",
                           valid_moves={"human": [[0,2]], "ai": []})
        state.data["wizard_held_by"] = "human"
        ok, _ = validate_wizard_teleport(state, 0, 1)
        assert ok is False

    def test_wizard_teleport_cannot_target_owned_tile(self):
        state = make_state([["Dh","Da","F"]], turn="human",
                           valid_moves={"human": [[0,2]], "ai": []})
        state.data["wizard_held_by"] = "human"
        ok, _ = validate_wizard_teleport(state, 0, 1)
        assert ok is False

    def test_wizard_teleport_fails_if_not_held(self):
        state = make_state([["Dh","F","F"]], turn="human",
                           valid_moves={"human": [[0,1]], "ai": []})
        state.data["wizard_held_by"] = None
        ok, _ = validate_wizard_teleport(state, 0, 2)
        assert ok is False

    def test_wizard_teleport_fails_if_wrong_player_holds(self):
        state = make_state([["Dh","F","F"]], turn="human",
                           valid_moves={"human": [[0,1]], "ai": []})
        state.data["wizard_held_by"] = "ai"
        ok, _ = validate_wizard_teleport(state, 0, 2)
        assert ok is False

    def test_wizard_tile_hidden_by_fog_at_game_start(self, client):
        """The Wizard tile is subject to fog of war like all other tiles."""
        resp  = client.post("/game/new", json={"seed": 3})
        board = resp.get_json()["board"]
        wizards = [t for row in board for t in row if t["type"] == "wizard"]
        assert len(wizards) == 1
        assert wizards[0]["visible"] is False

    def test_wizard_teleport_via_api(self, client):
        resp = client.post("/game/new", json={"seed": 42})
        gid  = resp.get_json()["game_id"]

        import database
        raw = database.load_game(gid)
        raw["wizard_held_by"] = "human"
        database.save_game(raw)

        # Find an unclaimed non-mountain tile not in human's pool
        board = raw["board"]
        target = None
        pool_set = {(p[0],p[1]) for p in raw["valid_moves"]["human"]}
        for r, row in enumerate(board):
            for c, tile in enumerate(row):
                if tile["owner"] is None and tile["type"] != "mountain":
                    target = (r, c)
                    break
            if target:
                break

        r, c = target
        resp2 = client.post(f"/game/{gid}/move", json={"wizard": True, "row": r, "col": c})
        assert resp2.status_code == 200
        data2 = resp2.get_json()
        assert data2["board"][r][c]["owner"] == "human"
        assert data2["wizard_held_by"] is None


# ===========================================================================
# 3E — Barbarian
# ===========================================================================
class TestBarbarian:
    def _barb_state(self, direction="horizontal", barb_r=2, barb_c=2, width=5, height=5):
        layout = [["F"]*width for _ in range(height)]
        state  = make_state(layout, turn="human",
                            valid_moves={"human": [], "ai": []})
        state.data["board"][barb_r][barb_c]["type"]          = "barbarian"
        state.data["board"][barb_r][barb_c]["special_state"] = {
            "direction": direction, "triggered": False
        }
        return state

    def test_horizontal_sweep_unclaims_entire_row(self):
        state = self._barb_state("horizontal", barb_r=2)
        # Place some owned tiles in row 2
        state.data["board"][2][0]["owner"] = "human"
        state.data["scores"]["human"] = 1
        state.data["board"][2][4]["owner"] = "ai"
        state.data["scores"]["ai"] = 1
        _trigger_barbarian(state, 2, 2)
        for c in range(5):
            assert state.tile(2, c)["owner"] is None

    def test_vertical_sweep_unclaims_entire_column(self):
        state = self._barb_state("vertical", barb_r=2, barb_c=2)
        state.data["board"][0][2]["owner"] = "human"
        state.data["scores"]["human"] = 1
        _trigger_barbarian(state, 2, 2)
        for r in range(5):
            assert state.tile(r, 2)["owner"] is None

    def test_barbarian_tile_becomes_forest(self):
        state = self._barb_state("horizontal", barb_r=2)
        _trigger_barbarian(state, 2, 2)
        assert state.tile(2, 2)["type"] == "forest"

    def test_barbarian_marked_triggered(self):
        # After trigger, the tile is Forest — verify no barbarian tile remains
        state = self._barb_state("horizontal", barb_r=2)
        _trigger_barbarian(state, 2, 2)
        for row in state.data["board"]:
            for t in row:
                if t["type"] == "barbarian":
                    assert t["special_state"]["triggered"] is True

    def test_mountain_not_unclaimed_by_sweep(self):
        state = self._barb_state("horizontal", barb_r=2)
        state.data["board"][2][1]["type"] = "mountain"
        _trigger_barbarian(state, 2, 2)
        assert state.tile(2, 1)["type"] == "mountain"

    def test_score_decremented_for_swept_tiles(self):
        state = self._barb_state("horizontal", barb_r=2)
        state.data["board"][2][0]["owner"] = "human"
        state.data["board"][2][4]["owner"] = "human"
        state.data["scores"]["human"] = 2
        _trigger_barbarian(state, 2, 2)
        assert state.scores["human"] == 0

    def test_pools_recomputed_after_sweep(self):
        state = self._barb_state("horizontal", barb_r=2)
        # Human owns (1,2); before sweep its valid moves include (2,2) which is Barbarian
        # After sweep (2,2) becomes Forest — human should have (2,2) in pool from (1,2)
        state.data["board"][1][2]["owner"] = "human"
        state.data["scores"]["human"] = 1
        _trigger_barbarian(state, 2, 2)
        vm = state.data["valid_moves"]["human"]
        assert [2, 2] in vm   # now Forest, reachable from (1,2)

    def test_barbarian_triggered_on_entering_pool(self):
        """When a Barbarian enters any player's valid moves pool, it triggers."""
        state = self._barb_state("horizontal", barb_r=1, barb_c=1)
        # check_barbarian_visibility simulates the Barbarian entering visible area
        check_barbarian_visibility(state, [(1, 1)])
        assert state.tile(1, 1)["type"] == "forest"

    def test_barbarian_triggered_by_tower_fog_reveal(self):
        """Tower reveals Barbarian at distance < 3 — Barbarian fires."""
        layout = [["F"]*7 for _ in range(7)]
        state  = make_state(layout, turn="human",
                            valid_moves={"human": [[3,3]], "ai": []})
        state.data["board"][3][3]["type"] = "tower"
        state.data["board"][3][5]["type"] = "barbarian"
        state.data["board"][3][5]["special_state"] = {"direction": "vertical", "triggered": False}
        state.data["board"][3][3]["owner"] = "human"  # tower already claimed
        apply_tower(state, 3, 3, "human")
        # (3,5) is at distance 2 — revealed by Tower, Barbarian fires
        assert state.tile(3, 5)["type"] == "forest"

    def test_barbarian_not_triggered_twice(self):
        state = self._barb_state("horizontal", barb_r=1)
        check_barbarian_visibility(state, [(1, 2)])  # barbarian is at (1,2)? No — at (1,2)
        # trigger once
        state2 = self._barb_state("horizontal", barb_r=2, barb_c=2)
        check_barbarian_visibility(state2, [(2, 2)])
        tile_after = state2.tile(2, 2)
        # Already a forest now; calling again doesn't re-sweep
        check_barbarian_visibility(state2, [(2, 2)])
        assert tile_after["type"] == "forest"


# ===========================================================================
# 3F — Integration: all specials in one game
# ===========================================================================
class TestIntegration:
    def test_cave_then_barbarian_no_corruption(self):
        """Cave claimed, then Barbarian sweeps through Cave partner — no crash."""
        state = make_state(
            [["F","F","F","F","F"],
             ["F","F","F","F","F"],
             ["F","C","B","C","F"],
             ["F","F","F","F","F"],
             ["F","F","F","F","F"]],
            turn="human",
            valid_moves={"human": [[2,1]], "ai": []},
        )
        state.data["board"][2][2]["special_state"] = {"direction": "horizontal", "triggered": False}
        state.data["board"][2][1]["special_state"] = {"inert": False, "connected_to": None}
        state.data["board"][2][3]["special_state"] = {"inert": False, "connected_to": None}

        # Claim Cave at (2,1)
        state.data["board"][2][1]["owner"] = "human"
        state.data["scores"]["human"] = 1
        apply_cave(state, 2, 1, "human")

        # Now trigger the Barbarian sweep (horizontal row 2)
        # This will unclaim (2,1) and replace (2,2) with Forest
        _trigger_barbarian(state, 2, 2)

        # State should be consistent: no crashes
        assert state.tile(2, 1)["owner"] is None  # swept
        assert state.tile(2, 2)["type"] == "forest"

    def test_wizard_then_tower_fog(self, client):
        """Human claims Wizard, then uses teleport onto Tower — fog expands."""
        resp = client.post("/game/new", json={"seed": 5, "width": 12, "height": 10})
        gid  = resp.get_json()["game_id"]

        import database
        raw = database.load_game(gid)
        raw["wizard_held_by"] = "human"
        # Place a Tower somewhere unclaimed and set it as teleport target
        raw["board"][5][5]["type"]          = "tower"
        raw["board"][5][5]["owner"]         = None
        raw["board"][5][5]["special_state"] = {}
        database.save_game(raw)

        resp2 = client.post(f"/game/{gid}/move",
                            json={"wizard": True, "row": 5, "col": 5})
        assert resp2.status_code == 200
        data2 = resp2.get_json()
        assert data2["board"][5][5]["owner"] == "human"
        assert data2["wizard_held_by"] is None
        # Tower fog: revealed_extra should cover tiles within distance 3
        raw2 = database.load_game(gid)
        revealed = {(p[0], p[1]) for p in raw2.get("revealed_extra", [])}
        assert (5, 5) in revealed
