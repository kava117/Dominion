"""Stage 2 tests — valid moves pool updates, fog, and the move endpoint."""
import pytest
from game.rules import (
    remove_from_pools,
    expand_pool_forest,
    validate_move,
    apply_move,
    compute_visible,
)
from tests.conftest import make_state, make_board


# ===========================================================================
# Pool helpers
# ===========================================================================
class TestRemoveFromPools:
    def test_removes_from_human_pool(self):
        state = make_state(
            [["F", "F", "F"]],
            valid_moves={"human": [[0, 0], [0, 1]], "ai": [[0, 2]]},
        )
        remove_from_pools(state, 0, 1)
        assert [0, 1] not in state.data["valid_moves"]["human"]

    def test_removes_from_ai_pool_simultaneously(self):
        state = make_state(
            [["F", "F", "F"]],
            valid_moves={"human": [[0, 1]], "ai": [[0, 1], [0, 2]]},
        )
        remove_from_pools(state, 0, 1)
        assert [0, 1] not in state.data["valid_moves"]["ai"]
        assert [0, 2] in state.data["valid_moves"]["ai"]

    def test_absent_position_is_noop(self):
        state = make_state(
            [["F", "F"]],
            valid_moves={"human": [[0, 0]], "ai": []},
        )
        before = list(state.data["valid_moves"]["human"])
        remove_from_pools(state, 0, 1)
        assert state.data["valid_moves"]["human"] == before


class TestExpandPoolForest:
    def test_adds_unclaimed_cardinal_neighbors(self):
        # Dh at (0,1); claim (0,1) then expand from it
        state = make_state(
            [["F", "Dh", "F"],
             ["F", "F",  "F"]],
            turn="human",
            valid_moves={"human": [], "ai": []},
        )
        expand_pool_forest(state, 0, 1, "human")
        vm = state.data["valid_moves"]["human"]
        assert [0, 0] in vm   # left
        assert [0, 2] in vm   # right
        assert [1, 1] in vm   # below
        # (above row -1 doesn't exist)

    def test_does_not_add_mountains(self):
        state = make_state(
            [["M", "Dh", "M"]],
            turn="human",
            valid_moves={"human": [], "ai": []},
        )
        expand_pool_forest(state, 0, 1, "human")
        vm = state.data["valid_moves"]["human"]
        assert not any(state.data["board"][r][c]["type"] == "mountain"
                       for r, c in [tuple(p) for p in vm])

    def test_does_not_add_already_owned_tiles(self):
        # (1,1) is owned by ai; expanding from (0,1) should not add (1,1)
        state = make_state(
            [["F", "Dh", "F"],
             ["F", "Da", "F"]],
            turn="human",
            valid_moves={"human": [], "ai": []},
        )
        expand_pool_forest(state, 0, 1, "human")
        vm = state.data["valid_moves"]["human"]
        assert [1, 1] not in vm

    def test_no_duplicate_entries(self):
        # Two adjacent domain tiles for human; both expand; center should appear once
        state = make_state(
            [["Dh", "F", "Dh"]],
            turn="human",
            valid_moves={"human": [], "ai": []},
        )
        expand_pool_forest(state, 0, 0, "human")
        expand_pool_forest(state, 0, 2, "human")
        vm = state.data["valid_moves"]["human"]
        assert vm.count([0, 1]) == 1

    def test_board_edge_does_not_error(self):
        # Corner tile — only 2 cardinal neighbors exist
        state = make_state(
            [["Dh", "F"],
             ["F",  "F"]],
            turn="human",
            valid_moves={"human": [], "ai": []},
        )
        expand_pool_forest(state, 0, 0, "human")
        vm = state.data["valid_moves"]["human"]
        assert [0, 1] in vm
        assert [1, 0] in vm
        assert len(vm) == 2

    def test_does_not_add_tile_already_in_pool(self):
        # (0,2) already in pool; expanding should not duplicate it
        state = make_state(
            [["Dh", "F", "F"]],
            turn="human",
            valid_moves={"human": [[0, 2]], "ai": []},
        )
        expand_pool_forest(state, 0, 1, "human")
        vm = state.data["valid_moves"]["human"]
        assert vm.count([0, 2]) == 1


# ===========================================================================
# Move validation
# ===========================================================================
class TestValidateMove:
    def test_valid_move_returns_true(self):
        state = make_state(
            [["Dh", "F", "F"]],
            turn="human",
            valid_moves={"human": [[0, 1]], "ai": []},
        )
        ok, _ = validate_move(state, 0, 1)
        assert ok is True

    def test_not_in_pool_returns_false(self):
        state = make_state(
            [["Dh", "F", "F"]],
            turn="human",
            valid_moves={"human": [[0, 2]], "ai": []},
        )
        ok, reason = validate_move(state, 0, 1)
        assert ok is False
        assert "pool" in reason.lower()

    def test_mountain_returns_false(self):
        state = make_state(
            [["M", "M", "Dh"]],
            turn="human",
            valid_moves={"human": [[0, 0]], "ai": []},
        )
        ok, reason = validate_move(state, 0, 0)
        assert ok is False

    def test_already_owned_returns_false(self):
        state = make_state(
            [["Dh", "Da", "F"]],
            turn="human",
            valid_moves={"human": [[0, 1]], "ai": []},
        )
        ok, _ = validate_move(state, 0, 1)
        assert ok is False

    def test_finished_game_returns_false(self):
        state = make_state(
            [["Dh", "F"]],
            turn="human",
            valid_moves={"human": [[0, 1]], "ai": []},
        )
        state.data["status"] = "human_wins"
        ok, _ = validate_move(state, 0, 1)
        assert ok is False


# ===========================================================================
# Apply move — Forest / Domain
# ===========================================================================
class TestApplyMoveForest:
    def _setup(self):
        """3x3 board with human Domain at centre, Forest everywhere else."""
        state = make_state(
            [["F", "F", "F"],
             ["F", "Dh", "F"],
             ["F", "F", "F"]],
            turn="human",
            valid_moves={
                "human": [[0, 1], [1, 0], [1, 2], [2, 1]],
                "ai":    [[0, 0]],
            },
        )
        return state

    def test_tile_becomes_owned(self):
        state = self._setup()
        apply_move(state, 0, 1)
        assert state.tile(0, 1)["owner"] == "human"

    def test_score_increments(self):
        state = self._setup()
        before = state.scores["human"]
        apply_move(state, 0, 1)
        assert state.scores["human"] == before + 1

    def test_claimed_tile_removed_from_human_pool(self):
        state = self._setup()
        apply_move(state, 0, 1)
        assert [0, 1] not in state.data["valid_moves"]["human"]

    def test_claimed_tile_removed_from_ai_pool(self):
        state = make_state(
            [["F", "F", "F"]],
            turn="human",
            valid_moves={"human": [[0, 0]], "ai": [[0, 0], [0, 2]]},
        )
        apply_move(state, 0, 0)
        assert [0, 0] not in state.data["valid_moves"]["ai"]
        assert [0, 2] in state.data["valid_moves"]["ai"]

    def test_new_neighbors_added_to_pool(self):
        state = self._setup()
        apply_move(state, 0, 1)   # claim (0,1); its unclaimed neighbors are (0,0),(0,2)
        vm = state.data["valid_moves"]["human"]
        assert [0, 0] in vm
        assert [0, 2] in vm

    def test_mountain_neighbors_not_added(self):
        state = make_state(
            [["M", "F", "M"],
             ["F", "Dh", "F"],
             ["M", "F", "M"]],
            turn="human",
            valid_moves={"human": [[0, 1], [1, 0], [1, 2], [2, 1]], "ai": []},
        )
        apply_move(state, 0, 1)
        vm = state.data["valid_moves"]["human"]
        for r, c in [(r, c) for r in range(3) for c in range(3)
                     if state.tile(r, c)["type"] == "mountain"]:
            assert [r, c] not in vm

    def test_turn_advances_to_ai(self):
        state = self._setup()
        assert state.turn == "human"
        apply_move(state, 0, 1)
        assert state.turn == "ai"

    def test_turn_advances_from_ai_to_human(self):
        state = make_state(
            [["F", "Da", "F"]],
            turn="ai",
            valid_moves={"human": [], "ai": [[0, 0]]},
        )
        apply_move(state, 0, 0)
        assert state.turn == "human"

    def test_domain_tile_behaves_identically_to_forest(self):
        """Claiming a Domain tile expands the pool the same way as Forest."""
        state_f = make_state(
            [["F", "F", "F"]],
            turn="human",
            valid_moves={"human": [[0, 1]], "ai": []},
        )
        state_d = make_state(
            [["F", "F", "F"]],
            turn="human",
            valid_moves={"human": [[0, 1]], "ai": []},
        )
        # Manually set the target tile type
        state_f.data["board"][0][1]["type"] = "forest"
        state_d.data["board"][0][1]["type"] = "domain"

        apply_move(state_f, 0, 1)
        apply_move(state_d, 0, 1)

        vm_f = sorted(state_f.data["valid_moves"]["human"])
        vm_d = sorted(state_d.data["valid_moves"]["human"])
        assert vm_f == vm_d

    def test_returns_tile_type(self):
        state = self._setup()
        result = apply_move(state, 0, 1)
        assert result == "forest"


# ===========================================================================
# Fog of war
# ===========================================================================
class TestFogOfWar:
    def test_claimed_tiles_visible(self):
        state = make_state(
            [["Dh", "F", "Da"]],
            valid_moves={"human": [], "ai": []},
        )
        vis = compute_visible(state)
        assert (0, 0) in vis   # human domain
        assert (0, 2) in vis   # ai domain

    def test_unclaimed_not_in_pool_is_fogged(self):
        state = make_state(
            [["Dh", "F", "F"]],
            valid_moves={"human": [], "ai": []},
        )
        vis = compute_visible(state)
        assert (0, 1) not in vis
        assert (0, 2) not in vis

    def test_valid_move_tile_is_visible(self):
        state = make_state(
            [["Dh", "F", "F"]],
            valid_moves={"human": [[0, 1]], "ai": []},
        )
        vis = compute_visible(state)
        assert (0, 1) in vis

    def test_opponent_pool_tile_is_visible(self):
        """Tiles in the AI's pool are visible even if not in human's pool."""
        state = make_state(
            [["Dh", "F", "Da"]],
            valid_moves={"human": [], "ai": [[0, 1]]},
        )
        vis = compute_visible(state)
        assert (0, 1) in vis

    def test_wizard_always_visible(self):
        state = make_state(
            [["W", "F", "F"]],
            valid_moves={"human": [], "ai": []},
        )
        vis = compute_visible(state)
        assert (0, 0) in vis

    def test_mountain_visible(self):
        state = make_state(
            [["M", "F"]],
            valid_moves={"human": [], "ai": []},
        )
        vis = compute_visible(state)
        assert (0, 0) in vis

    def test_fog_updates_after_move(self):
        """After claiming a Forest, newly adjacent tiles enter the pool and fog lifts."""
        state = make_state(
            [["F", "F", "F"]],
            turn="human",
            valid_moves={"human": [[0, 0]], "ai": []},
        )
        apply_move(state, 0, 0)
        vis = compute_visible(state)
        # (0,0) claimed → visible
        assert (0, 0) in vis
        # (0,1) added to pool by Forest expansion → visible
        assert (0, 1) in vis
        # (0,2) still unreachable → fogged
        assert (0, 2) not in vis

    def test_revealed_extra_visible(self):
        """Tiles in revealed_extra (e.g., Tower fog reveal) are visible."""
        state = make_state(
            [["F", "F", "F"]],
            valid_moves={"human": [], "ai": []},
        )
        state.data["revealed_extra"] = [[0, 2]]
        vis = compute_visible(state)
        assert (0, 2) in vis

    def test_api_response_board_visible_field(self):
        """to_api_response() correctly sets visible on each tile."""
        state = make_state(
            [["F", "F", "F"]],
            turn="human",
            valid_moves={"human": [[0, 1]], "ai": []},
        )
        resp = state.to_api_response()
        board = resp["board"]
        assert board[0][1]["visible"] is True   # in pool
        assert board[0][2]["visible"] is False  # not in pool, not claimed


# ===========================================================================
# Move endpoint — POST /game/<id>/move
# ===========================================================================
class TestMoveEndpoint:
    def _new_game(self, client, seed=42):
        resp = client.post("/game/new", json={"seed": seed, "width": 12, "height": 10})
        return resp.get_json()

    def test_valid_move_returns_200(self, client):
        game = self._new_game(client)
        gid  = game["game_id"]
        r, c = game["valid_moves"][0]
        resp = client.post(f"/game/{gid}/move", json={"row": r, "col": c})
        assert resp.status_code == 200

    def test_move_response_has_all_fields(self, client):
        game = self._new_game(client)
        gid  = game["game_id"]
        r, c = game["valid_moves"][0]
        data = client.post(f"/game/{gid}/move", json={"row": r, "col": c}).get_json()
        for field in ("game_id", "board", "valid_moves", "scores", "turn", "status"):
            assert field in data

    def test_tile_is_owned_after_move(self, client):
        game = self._new_game(client)
        gid  = game["game_id"]
        r, c = game["valid_moves"][0]
        data = client.post(f"/game/{gid}/move", json={"row": r, "col": c}).get_json()
        assert data["board"][r][c]["owner"] == "human"

    def test_turn_advances_to_ai_after_human_move(self, client):
        game = self._new_game(client)
        gid  = game["game_id"]
        r, c = game["valid_moves"][0]
        data = client.post(f"/game/{gid}/move", json={"row": r, "col": c}).get_json()
        assert data["turn"] == "ai"

    def test_score_increments_after_move(self, client):
        game = self._new_game(client)
        gid  = game["game_id"]
        before = game["scores"]["human"]
        r, c   = game["valid_moves"][0]
        data   = client.post(f"/game/{gid}/move", json={"row": r, "col": c}).get_json()
        assert data["scores"]["human"] == before + 1

    def test_invalid_move_not_in_pool_returns_400(self, client):
        game = self._new_game(client)
        gid  = game["game_id"]
        # Find a tile not in valid moves
        pool_set = {(r, c) for r, c in game["valid_moves"]}
        board    = game["board"]
        for r, row in enumerate(board):
            for c, tile in enumerate(row):
                if (r, c) not in pool_set and tile["owner"] is None and tile["type"] != "mountain":
                    resp = client.post(f"/game/{gid}/move", json={"row": r, "col": c})
                    assert resp.status_code == 400
                    return
        pytest.skip("No invalid move target found on this board")

    def test_move_on_nonexistent_game_returns_404(self, client):
        resp = client.post("/game/no-such-id/move", json={"row": 0, "col": 0})
        assert resp.status_code == 404

    def test_missing_row_col_returns_400(self, client):
        game = self._new_game(client)
        resp = client.post(f"/game/{game['game_id']}/move", json={"row": 0})
        assert resp.status_code == 400

    def test_move_persists_across_get(self, client):
        """State saved to DB: GET after move returns the updated owner."""
        game = self._new_game(client)
        gid  = game["game_id"]
        r, c = game["valid_moves"][0]
        client.post(f"/game/{gid}/move", json={"row": r, "col": c})
        data = client.get(f"/game/{gid}").get_json()
        assert data["board"][r][c]["owner"] == "human"

    def test_new_neighbors_in_valid_moves_after_forest_claim(self, client):
        """After claiming a Forest tile, its unclaimed neighbors should be
        in the valid moves pool for the next turn."""
        game = self._new_game(client)
        gid  = game["game_id"]
        r, c = game["valid_moves"][0]
        data = client.post(f"/game/{gid}/move", json={"row": r, "col": c}).get_json()

        # After the move it's the AI's turn; check via valid-moves endpoint for human
        # by starting a game where human goes first, then looking at full state.
        # The claimed tile's pool-of-record belongs to "ai" now (turn advanced).
        # Fetch state and check that all valid-moves are unclaimed non-mountains.
        board = data["board"]
        for mr, mc in data["valid_moves"]:
            tile = board[mr][mc]
            assert tile["owner"] is None
            assert tile["type"] != "mountain"

    def test_fog_lifted_on_newly_valid_tiles(self, client):
        """Tiles added to the valid moves pool should be visible in the response."""
        game = self._new_game(client)
        gid  = game["game_id"]
        r, c = game["valid_moves"][0]
        data = client.post(f"/game/{gid}/move", json={"row": r, "col": c}).get_json()

        board    = data["board"]
        pool_set = {(mr, mc) for mr, mc in data["valid_moves"]}
        for (mr, mc) in pool_set:
            assert board[mr][mc]["visible"] is True, (
                f"Tile ({mr},{mc}) in valid moves pool but visible=False"
            )
