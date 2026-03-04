"""Stage 4 tests — win conditions and turn-skip logic."""
import pytest
from game.win import check_win, _resolve_status, _maybe_skip_turn
from game.rules import apply_move
from tests.conftest import make_state


# ---------------------------------------------------------------------------
# Helper: build a state that is almost complete
# ---------------------------------------------------------------------------
def _near_end_state(human_score, ai_score, claimable_total,
                    human_vm=None, ai_vm=None, turn="human"):
    """Minimal state with controlled scores, pool sizes, and claimable total."""
    layout = [["F"] * claimable_total]
    state  = make_state(layout, turn=turn,
                        valid_moves={
                            "human": human_vm or [],
                            "ai":    ai_vm    or [],
                        })
    state.data["scores"]          = {"human": human_score, "ai": ai_score}
    state.data["claimable_total"] = claimable_total
    return state


# ===========================================================================
# Standard end
# ===========================================================================
class TestStandardEnd:
    def test_human_wins_when_all_tiles_claimed(self):
        state = _near_end_state(7, 3, claimable_total=10, human_vm=[], ai_vm=[])
        check_win(state)
        assert state.status == "human_wins"

    def test_ai_wins_when_all_tiles_claimed(self):
        state = _near_end_state(3, 7, claimable_total=10, human_vm=[], ai_vm=[])
        check_win(state)
        assert state.status == "ai_wins"

    def test_tie_when_all_tiles_claimed_equal_scores(self):
        state = _near_end_state(5, 5, claimable_total=10, human_vm=[], ai_vm=[])
        check_win(state)
        assert state.status == "tie"

    def test_no_winner_when_tiles_remain_and_moves_exist(self):
        state = _near_end_state(3, 3, claimable_total=10,
                                human_vm=[[0,6]], ai_vm=[[0,7]])
        check_win(state)
        assert state.status == "in_progress"

    def test_ends_when_nobody_has_moves_even_if_tiles_unclaimed(self):
        # Both pools empty but tiles unclaimed → nobody can progress → end
        state = _near_end_state(4, 4, claimable_total=10, human_vm=[], ai_vm=[])
        check_win(state)
        assert state.status == "tie"

    def test_human_wins_when_nobody_has_moves_unequal(self):
        state = _near_end_state(6, 4, claimable_total=10, human_vm=[], ai_vm=[])
        check_win(state)
        assert state.status == "human_wins"


# ===========================================================================
# Dominant end
# ===========================================================================
class TestDominantEnd:
    def test_human_dominant_ai_no_moves(self):
        # 10 claimable tiles; human has 6 (> 50 %), AI has 0 valid moves
        state = _near_end_state(6, 2, claimable_total=10,
                                human_vm=[[0,8]], ai_vm=[])
        check_win(state)
        assert state.status == "human_wins"

    def test_ai_dominant_human_no_moves(self):
        state = _near_end_state(2, 6, claimable_total=10,
                                human_vm=[], ai_vm=[[0,8]])
        check_win(state)
        assert state.status == "ai_wins"

    def test_dominant_requires_exactly_over_half(self):
        # 10 tiles; human has exactly 5 (= 50 %) — NOT dominant
        state = _near_end_state(5, 3, claimable_total=10,
                                human_vm=[[0,8]], ai_vm=[])
        check_win(state)
        assert state.status == "in_progress"

    def test_dominant_not_triggered_when_opponent_has_moves(self):
        state = _near_end_state(6, 2, claimable_total=10,
                                human_vm=[[0,8]], ai_vm=[[0,9]])
        check_win(state)
        assert state.status == "in_progress"

    def test_dominant_odd_total(self):
        # 11 claimable tiles; threshold = 5.5; human needs >= 6
        state = _near_end_state(6, 2, claimable_total=11,
                                human_vm=[[0,0]], ai_vm=[])
        check_win(state)
        assert state.status == "human_wins"

    def test_dominant_with_5_out_of_11_not_triggered(self):
        state = _near_end_state(5, 2, claimable_total=11,
                                human_vm=[[0,0]], ai_vm=[])
        check_win(state)
        assert state.status == "in_progress"


# ===========================================================================
# Turn skip
# ===========================================================================
class TestTurnSkip:
    def test_active_player_skipped_when_no_moves(self):
        state = _near_end_state(2, 2, claimable_total=10,
                                human_vm=[], ai_vm=[[0,4]], turn="human")
        state.data["status"] = "in_progress"
        _maybe_skip_turn(state)
        assert state.turn == "ai"

    def test_no_skip_when_active_player_has_moves(self):
        state = _near_end_state(2, 2, claimable_total=10,
                                human_vm=[[0,4]], ai_vm=[], turn="human")
        _maybe_skip_turn(state)
        assert state.turn == "human"

    def test_check_win_skips_turn_within_in_progress(self):
        # After check_win, if game still in_progress and active player has no
        # moves, turn should pass to opponent automatically.
        state = _near_end_state(3, 3, claimable_total=10,
                                human_vm=[], ai_vm=[[0,4]], turn="human")
        check_win(state)
        assert state.status == "in_progress"
        assert state.turn == "ai"   # skipped to AI


# ===========================================================================
# Win condition integrated into apply_move
# ===========================================================================
class TestWinViaApplyMove:
    def test_last_tile_triggers_standard_win(self):
        """Claiming the final tile ends the game."""
        # 1×3 board: human owns (0,0), AI owns (0,2), (0,1) is last tile.
        state = make_state(
            [["Dh", "F", "Da"]],
            turn="human",
            valid_moves={"human": [[0, 1]], "ai": []},
        )
        state.data["claimable_total"] = 3
        apply_move(state, 0, 1)
        assert state.status in ("human_wins", "ai_wins", "tie")

    def test_dominant_win_triggers_via_apply_move(self):
        """Reaching > 50 % when opponent has no moves ends the game."""
        # 5 claimable tiles, threshold = 2.5; human gets 3rd tile → dominant
        state = make_state(
            [["Dh", "F", "Dh", "Da", "Da"]],
            turn="human",
            valid_moves={"human": [[0, 1]], "ai": []},
        )
        state.data["claimable_total"] = 5
        state.data["scores"]          = {"human": 2, "ai": 2}
        apply_move(state, 0, 1)
        assert state.status == "human_wins"

    def test_game_does_not_end_mid_game(self):
        """Plenty of tiles and moves left — game stays in_progress."""
        state = make_state(
            [["Dh","F","F","F","F","Da"]],
            turn="human",
            valid_moves={"human": [[0,1]], "ai": [[0,4]]},
        )
        state.data["claimable_total"] = 6
        apply_move(state, 0, 1)
        assert state.status == "in_progress"

    def test_status_stays_finished_on_second_check(self):
        """Once the game is over, check_win is a no-op."""
        from game.win import check_win
        state = _near_end_state(7, 3, claimable_total=10)
        check_win(state)
        assert state.status == "human_wins"
        state.data["scores"]["ai"] = 8  # artificially change scores
        check_win(state)
        assert state.status == "human_wins"  # unchanged

    def test_turn_skip_integrated_into_apply_move(self):
        """After a move, if the new active player has no moves, they're skipped."""
        # Human moves; AI has no valid moves but game not over; turn skips back to human
        state = make_state(
            [["Dh","F","F","Da","Da"]],
            turn="human",
            valid_moves={"human": [[0,1]], "ai": []},
        )
        state.data["claimable_total"] = 5
        state.data["scores"]          = {"human": 1, "ai": 2}
        apply_move(state, 0, 1)
        # After human claims (0,1): human=2, ai=2, 1 tile unclaimed.
        # AI has no moves → turn skipped → back to human
        assert state.turn == "human"


# ===========================================================================
# Win via API endpoint
# ===========================================================================
class TestWinViaAPI:
    def test_game_over_status_in_response(self, client):
        resp = client.post("/game/new", json={"seed": 42})
        gid  = resp.get_json()["game_id"]

        import database
        raw = database.load_game(gid)
        # Force game to near-end: one tile left, human already dominant
        raw["scores"]          = {"human": 60, "ai": 10}
        raw["claimable_total"] = 71
        raw["valid_moves"]     = {"human": [[0, 0]], "ai": []}
        raw["board"][0][0]["type"]  = "forest"
        raw["board"][0][0]["owner"] = None
        database.save_game(raw)

        resp2 = client.post(f"/game/{gid}/move", json={"row": 0, "col": 0})
        data2 = resp2.get_json()
        assert data2["status"] in ("human_wins", "tie")

    def test_move_rejected_after_game_over(self, client):
        resp = client.post("/game/new", json={"seed": 42})
        gid  = resp.get_json()["game_id"]

        import database
        raw = database.load_game(gid)
        raw["status"] = "human_wins"
        database.save_game(raw)

        # Any move should be rejected
        vm = raw["valid_moves"]["human"]
        if vm:
            r, c  = vm[0]
            resp2 = client.post(f"/game/{gid}/move", json={"row": r, "col": c})
            assert resp2.status_code == 400
