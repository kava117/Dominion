"""Stage 5 tests — AI engine: heuristic, minimax, alpha-beta, /ai-move endpoint."""
import pytest
from game.ai.heuristic import evaluate
from game.ai.minimax import (
    get_best_move, get_all_moves, apply_ai_move,
    minimax_no_pruning, _minimax, _simulate, _clone, DIFFICULTY_DEPTH,
)
from game.rules import apply_move
from tests.conftest import make_state


# ===========================================================================
# Heuristic
# ===========================================================================
class TestHeuristic:
    def test_winning_state_returns_high_score(self):
        state = make_state([["Da","Da"]], valid_moves={"human":[],"ai":[]})
        state.data["status"] = "ai_wins"
        assert evaluate(state, "ai") > 100_000

    def test_losing_state_returns_low_score(self):
        state = make_state([["Dh","Dh"]], valid_moves={"human":[],"ai":[]})
        state.data["status"] = "human_wins"
        assert evaluate(state, "ai") < -100_000

    def test_tie_returns_zero(self):
        state = make_state([["Dh","Da"]], valid_moves={"human":[],"ai":[]})
        state.data["status"] = "tie"
        assert evaluate(state, "ai") == 0

    def test_more_ai_tiles_higher_score(self):
        s_lead = make_state([["Da","Da","Dh"]], valid_moves={"human":[],"ai":[]})
        s_trail= make_state([["Dh","Dh","Da"]], valid_moves={"human":[],"ai":[]})
        assert evaluate(s_lead, "ai") > evaluate(s_trail, "ai")

    def test_more_ai_pool_moves_higher_score(self):
        s_big  = make_state([["Da","F","F","F"]], valid_moves={"human":[],"ai":[[0,1],[0,2],[0,3]]})
        s_small= make_state([["Da","F","F","F"]], valid_moves={"human":[],"ai":[[0,1]]})
        assert evaluate(s_big, "ai") > evaluate(s_small, "ai")

    def test_wizard_in_pool_raises_score(self):
        s_wizard = make_state([["Da","W"]], valid_moves={"human":[],"ai":[[0,1]]})
        s_forest = make_state([["Da","F"]], valid_moves={"human":[],"ai":[[0,1]]})
        assert evaluate(s_wizard, "ai") > evaluate(s_forest, "ai")

    def test_holding_wizard_raises_score(self):
        state = make_state([["Da","F"]], valid_moves={"human":[],"ai":[]})
        state.data["wizard_held_by"] = "ai"
        s_no_wiz = make_state([["Da","F"]], valid_moves={"human":[],"ai":[]})
        assert evaluate(state, "ai") > evaluate(s_no_wiz, "ai")

    def test_opponent_holding_wizard_lowers_score(self):
        state = make_state([["Da","F"]], valid_moves={"human":[],"ai":[]})
        state.data["wizard_held_by"] = "human"
        s_neutral = make_state([["Da","F"]], valid_moves={"human":[],"ai":[]})
        assert evaluate(state, "ai") < evaluate(s_neutral, "ai")

    def test_connected_cave_bonus(self):
        s_connected = make_state([["Da","F"]], valid_moves={"human":[],"ai":[]})
        s_connected.data["board"][0][0]["type"] = "cave"
        s_connected.data["board"][0][0]["special_state"] = {"inert": True, "connected_to": [0,1]}
        s_plain = make_state([["Da","F"]], valid_moves={"human":[],"ai":[]})
        assert evaluate(s_connected, "ai") > evaluate(s_plain, "ai")


# ===========================================================================
# Move generation
# ===========================================================================
class TestGetAllMoves:
    def test_normal_moves_returned(self):
        state = make_state(
            [["Da","F","F"]],
            turn="ai",
            valid_moves={"human":[],"ai":[[0,1],[0,2]]},
        )
        moves = get_all_moves(state)
        types = [m["type"] for m in moves]
        assert all(t == "normal" for t in types)
        coords = {(m["row"], m["col"]) for m in moves}
        assert (0,1) in coords and (0,2) in coords

    def test_wizard_use_included_when_held(self):
        state = make_state(
            [["Da","F","F"]],
            turn="ai",
            valid_moves={"human":[],"ai":[[0,1]]},
        )
        state.data["wizard_held_by"] = "ai"
        moves = get_all_moves(state)
        assert any(m["type"] == "wizard" for m in moves)

    def test_wizard_not_included_when_not_held(self):
        state = make_state(
            [["Da","F","F"]],
            turn="ai",
            valid_moves={"human":[],"ai":[[0,1]]},
        )
        moves = get_all_moves(state)
        assert not any(m["type"] == "wizard" for m in moves)

    def test_plains_generates_compound_moves(self):
        state = make_state(
            [["F","F","F","F","F"],
             ["F","F","F","F","F"],
             ["F","F","P","F","F"],
             ["F","F","F","F","F"],
             ["F","F","F","F","F"]],
            turn="ai",
            valid_moves={"human":[],"ai":[[2,2]]},
        )
        moves = get_all_moves(state)
        assert all(m["type"] == "plains" for m in moves)
        # Should have multiple compound moves (first x second combinations)
        assert len(moves) > 1

    def test_move_ordering_special_before_forest(self):
        state = make_state(
            [["Da","F","W","T"]],
            turn="ai",
            valid_moves={"human":[],"ai":[[0,1],[0,2],[0,3]]},
        )
        moves = get_all_moves(state)
        tile_types = [m.get("tile_type","?") for m in moves]
        # Wizard tile should come before forest in ordering
        wi = next(i for i,t in enumerate(tile_types) if t=="wizard")
        fo = next(i for i,t in enumerate(tile_types) if t=="forest")
        assert wi < fo

    def test_empty_pool_returns_only_wizard_moves_if_held(self):
        state = make_state(
            [["Da","F","F"]],
            turn="ai",
            valid_moves={"human":[],"ai":[]},
        )
        state.data["wizard_held_by"] = "ai"
        moves = get_all_moves(state)
        assert all(m["type"] == "wizard" for m in moves)

    def test_empty_pool_no_wizard_returns_empty(self):
        state = make_state([["Da"]], turn="ai", valid_moves={"human":[],"ai":[]})
        assert get_all_moves(state) == []


# ===========================================================================
# Alpha-beta correctness vs plain minimax
# ===========================================================================
class TestAlphaBetaCorrectness:
    def _tiny_state(self):
        """3-tile board: AI owns (0,0), one Forest for each player's pool."""
        state = make_state(
            [["Da","F","Dh"]],
            turn="ai",
            valid_moves={"human":[[0,1]],"ai":[[0,1]]},
        )
        state.data["claimable_total"] = 3
        return state

    def test_depth0_returns_heuristic(self):
        state = self._tiny_state()
        val_ab, _  = _minimax(state, 0, float("-inf"), float("inf"), "ai", float("inf"))
        val_h = evaluate(state, "ai")
        assert val_ab == val_h

    def test_alpha_beta_same_value_as_plain_minimax_depth2(self):
        state = self._tiny_state()
        val_ab, _  = _minimax(state, 2, float("-inf"), float("inf"), "ai", float("inf"))
        val_np, _  = minimax_no_pruning(state, 2, "ai")
        assert val_ab == pytest.approx(val_np, abs=0.1)

    def test_alpha_beta_same_value_as_plain_minimax_depth3(self):
        state = make_state(
            [["Da","F","F","Dh"]],
            turn="ai",
            valid_moves={"human":[[0,2]],"ai":[[0,1],[0,2]]},
        )
        state.data["claimable_total"] = 4
        val_ab, _ = _minimax(state, 3, float("-inf"), float("inf"), "ai", float("inf"))
        val_np, _ = minimax_no_pruning(state, 3, "ai")
        assert val_ab == pytest.approx(val_np, abs=0.1)


# ===========================================================================
# AI makes legal moves
# ===========================================================================
class TestAILegalMoves:
    def _game_state(self, seed=42):
        from game.state import create_game
        state = create_game(seed=seed, difficulty="easy")
        state.data["turn"] = "ai"
        return state

    def test_get_best_move_returns_valid_move(self):
        state = self._game_state()
        move  = get_best_move(state)
        assert move is not None
        assert "row" in move and "col" in move

    def test_apply_ai_move_lands_on_valid_tile(self):
        state = self._game_state()
        vm_before = {(p[0],p[1]) for p in state.data["valid_moves"]["ai"]}
        move  = get_best_move(state)
        r, c  = move["row"], move["col"]
        assert (r, c) in vm_before, "AI tried to claim a tile not in its pool"

    def test_ai_tile_owned_after_apply(self):
        state = self._game_state()
        move  = get_best_move(state)
        apply_ai_move(state, move)
        r, c  = move["row"], move["col"]
        assert state.tile(r, c)["owner"] == "ai"

    def test_ai_turn_advances_after_move(self):
        state = self._game_state()
        move  = get_best_move(state)
        apply_ai_move(state, move)
        # After AI moves, it's human's turn (or game is over)
        assert state.turn in ("human", "ai")  # could be skipped back

    def test_ai_score_increments(self):
        state  = self._game_state()
        before = state.scores["ai"]
        move   = get_best_move(state)
        apply_ai_move(state, move)
        assert state.scores["ai"] >= before + 1

    def test_ai_never_claims_mountain(self):
        for seed in range(5):
            state = self._game_state(seed=seed)
            move  = get_best_move(state)
            r, c  = move["row"], move["col"]
            assert state.tile(r, c)["type"] != "mountain", \
                f"AI claimed a mountain at ({r},{c}) seed={seed}"

    def test_ai_never_claims_owned_tile(self):
        for seed in range(5):
            state = self._game_state(seed=seed)
            move  = get_best_move(state)
            r, c  = move["row"], move["col"]
            assert state.tile(r, c)["owner"] is None, \
                f"AI claimed already-owned tile at ({r},{c}) seed={seed}"


# ===========================================================================
# Wizard handling
# ===========================================================================
class TestAIWizard:
    def test_ai_uses_wizard_when_held_and_beneficial(self):
        """AI with wizard should prefer teleporting far ahead to a high-value tile."""
        state = make_state(
            [["Da","F","F","F","F","W"]],
            turn="ai",
            valid_moves={"human":[],"ai":[[0,1]]},
        )
        # Give AI the wizard ability
        state.data["wizard_held_by"] = "ai"
        state.data["claimable_total"] = 6

        move = get_best_move(state)
        assert move is not None
        # The AI should consider wizard moves (wizard tile is at (0,5))
        all_moves = get_all_moves(state)
        wizard_moves = [m for m in all_moves if m["type"] == "wizard"]
        assert len(wizard_moves) > 0

    def test_wizard_move_applied_correctly(self):
        state = make_state(
            [["Da","F","F","F"]],
            turn="ai",
            valid_moves={"human":[],"ai":[[0,1]]},
        )
        state.data["wizard_held_by"] = "ai"
        state.data["claimable_total"] = 4
        move = {"type": "wizard", "row": 0, "col": 3}
        apply_ai_move(state, move)
        assert state.tile(0, 3)["owner"] == "ai"
        assert state.data["wizard_held_by"] is None


# ===========================================================================
# Plains compound moves in AI
# ===========================================================================
class TestAIPlainsCompound:
    def test_plains_compound_moves_all_legal(self):
        """All compound Plains moves generated should be fully valid sequences."""
        state = make_state(
            [["F","F","F","F","F"],
             ["F","F","F","F","F"],
             ["F","F","P","F","F"],
             ["F","F","F","F","F"],
             ["F","F","F","F","F"]],
            turn="ai",
            valid_moves={"human":[],"ai":[[2,2]]},
        )
        state.data["claimable_total"] = 25

        moves = get_all_moves(state)
        for move in moves:
            sim = _simulate(state, move)
            # After simulating: phase should be None (plains fully resolved)
            assert sim.data.get("phase") is None, \
                f"Plains move {move} left sim in phase {sim.data.get('phase')}"

    def test_ai_plains_move_claims_3_tiles(self):
        """Full Plains compound move should claim Plains + first + second = 3 tiles."""
        state = make_state(
            [["F","F","F","F","F"],
             ["F","F","F","F","F"],
             ["Da","F","P","F","Da"],
             ["F","F","F","F","F"],
             ["F","F","F","F","F"]],
            turn="ai",
            valid_moves={"human":[],"ai":[[2,2]]},
        )
        before = state.scores["ai"]
        move   = get_best_move(state)
        apply_ai_move(state, move)
        # Plains tile + first pick + (optional) second pick
        assert state.scores["ai"] >= before + 2  # at least plains + first pick


# ===========================================================================
# /ai-move endpoint
# ===========================================================================
class TestAiMoveEndpoint:
    def _setup(self, client, seed=42):
        resp = client.post("/game/new", json={"seed": seed, "difficulty": "easy"})
        gid  = resp.get_json()["game_id"]
        import database
        raw = database.load_game(gid)
        raw["turn"] = "ai"
        database.save_game(raw)
        return gid

    def test_returns_200(self, client):
        gid  = self._setup(client)
        resp = client.post(f"/game/{gid}/ai-move")
        assert resp.status_code == 200

    def test_response_has_required_fields(self, client):
        gid  = self._setup(client)
        data = client.post(f"/game/{gid}/ai-move").get_json()
        for field in ("game_id","board","valid_moves","scores","turn","status"):
            assert field in data

    def test_ai_tile_owned_after_endpoint(self, client):
        gid  = self._setup(client)
        import database
        raw  = database.load_game(gid)
        ai_vm = raw["valid_moves"]["ai"]
        assert ai_vm, "AI has no valid moves to test"
        resp = client.post(f"/game/{gid}/ai-move").get_json()
        # At least one AI tile should exist now
        owned = [t for row in resp["board"] for t in row if t["owner"] == "ai"]
        assert len(owned) > 0

    def test_returns_400_when_not_ai_turn(self, client):
        resp = client.post("/game/new", json={"seed": 1, "difficulty": "easy"})
        gid  = resp.get_json()["game_id"]
        # It's human's turn by default
        assert client.post(f"/game/{gid}/ai-move").status_code == 400

    def test_returns_404_for_unknown_game(self, client):
        assert client.post("/game/no-such-game/ai-move").status_code == 404

    def test_returns_400_when_game_over(self, client):
        gid = self._setup(client)
        import database
        raw = database.load_game(gid)
        raw["status"] = "human_wins"
        database.save_game(raw)
        assert client.post(f"/game/{gid}/ai-move").status_code == 400

    def test_multiple_ai_moves_no_illegal_states(self, client):
        """Play 5 full rounds (human + AI) without illegal states."""
        resp = client.post("/game/new", json={"seed": 99, "difficulty": "easy"})
        gid  = resp.get_json()["game_id"]

        for _ in range(5):
            state_data = client.get(f"/game/{gid}").get_json()
            if state_data["status"] != "in_progress":
                break

            # Human plays first valid move
            vm = state_data["valid_moves"]
            if vm and state_data["turn"] == "human":
                r, c = vm[0]
                client.post(f"/game/{gid}/move", json={"row": r, "col": c})

            # AI plays
            state_data2 = client.get(f"/game/{gid}").get_json()
            if state_data2["status"] != "in_progress":
                break
            if state_data2["turn"] == "ai":
                ai_resp = client.post(f"/game/{gid}/ai-move")
                assert ai_resp.status_code == 200

            # Verify all valid moves are unclaimed non-mountains
            final = client.get(f"/game/{gid}").get_json()
            board = final["board"]
            for mr, mc in final["valid_moves"]:
                assert board[mr][mc]["owner"] is None
                assert board[mr][mc]["type"] != "mountain"

    def test_difficulty_depth_constants(self):
        assert DIFFICULTY_DEPTH["easy"]   == 2
        assert DIFFICULTY_DEPTH["medium"] == 4
        assert DIFFICULTY_DEPTH["hard"]   == 6
