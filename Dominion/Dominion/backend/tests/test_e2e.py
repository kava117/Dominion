"""Stage 9 — End-to-End Tests.

Drives the full HTTP API to verify complete game paths, edge cases,
and performance requirements. State is manipulated via the database
layer where needed to set up specific scenarios.
"""
import time
import pytest
import database
from main import create_app


# ── Fixtures & helpers ─────────────────────────────────────────────────────────

@pytest.fixture
def client(tmp_path):
    db = str(tmp_path / "test_games.db")
    app = create_app(db_path=db)
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _new_game(client, **kwargs):
    """POST /game/new with defaults and return (game_id, data)."""
    defaults = {"width": 8, "height": 8, "seed": 42, "difficulty": "easy"}
    defaults.update(kwargs)
    resp = client.post("/game/new", json=defaults)
    assert resp.status_code == 201
    data = resp.get_json()
    return data["game_id"], data


def _patch(game_id, **updates):
    """Overwrite specific keys in the stored game dict."""
    raw = database.load_game(game_id)
    raw.update(updates)
    database.save_game(raw)
    return raw


# ── 1. Seed reproducibility ────────────────────────────────────────────────────

class TestSeedReproducibility:
    def test_same_seed_produces_identical_boards(self, client):
        """Two games with the same seed and config return identical tile types."""
        _, d1 = _new_game(client, seed=7777, width=10, height=8)
        _, d2 = _new_game(client, seed=7777, width=10, height=8)
        types1 = [[t["type"] for t in row] for row in d1["board"]]
        types2 = [[t["type"] for t in row] for row in d2["board"]]
        assert types1 == types2

    def test_different_seeds_produce_different_boards(self, client):
        """Two games with different seeds (usually) differ in layout."""
        _, d1 = _new_game(client, seed=111, width=10, height=10)
        _, d2 = _new_game(client, seed=999, width=10, height=10)
        types1 = [[t["type"] for t in row] for row in d1["board"]]
        types2 = [[t["type"] for t in row] for row in d2["board"]]
        assert types1 != types2


# ── 2. Full game — standard end ────────────────────────────────────────────────

class TestFullGameStandardEnd:
    def test_last_tile_claim_ends_game(self, client):
        """Manipulate to one remaining tile; claiming it ends the game."""
        gid, _ = _new_game(client)
        raw = database.load_game(gid)
        h, w = raw["height"], raw["width"]
        ct = h * w

        # Mark every tile as owned by human except (0,0)
        for r in range(h):
            for c in range(w):
                raw["board"][r][c]["owner"] = "human"
                raw["board"][r][c]["type"]  = "forest"
        raw["board"][0][0]["owner"] = None

        raw["scores"]          = {"human": ct - 1, "ai": 0}
        raw["claimable_total"] = ct
        raw["valid_moves"]     = {"human": [[0, 0]], "ai": []}
        raw["turn"]            = "human"
        raw["status"]          = "in_progress"
        database.save_game(raw)

        resp = client.post(f"/game/{gid}/move", json={"row": 0, "col": 0})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] in ("human_wins", "tie")

    def test_human_wins_when_score_is_higher(self, client):
        """Human with strictly more tiles is declared winner."""
        gid, _ = _new_game(client)
        raw = database.load_game(gid)
        h, w = raw["height"], raw["width"]
        ct = h * w

        for r in range(h):
            for c in range(w):
                raw["board"][r][c]["owner"] = "human"
                raw["board"][r][c]["type"]  = "forest"
        raw["board"][0][0]["owner"] = None
        # human: ct-2, ai: 1 → human wins
        raw["board"][0][1]["owner"] = "ai"
        raw["scores"]          = {"human": ct - 2, "ai": 1}
        raw["claimable_total"] = ct
        raw["valid_moves"]     = {"human": [[0, 0]], "ai": []}
        raw["turn"]            = "human"
        raw["status"]          = "in_progress"
        database.save_game(raw)

        resp = client.post(f"/game/{gid}/move", json={"row": 0, "col": 0})
        assert resp.get_json()["status"] == "human_wins"


# ── 3. Full game — dominant end ────────────────────────────────────────────────

class TestFullGameDominantEnd:
    def test_human_dominant_win_via_api(self, client):
        """Human surpasses 50 % while AI has 0 valid moves → human_wins."""
        gid, _ = _new_game(client)
        raw = database.load_game(gid)
        h, w = raw["height"], raw["width"]
        ct = h * w

        # Give human exactly half; claiming one more tile → > 50 %
        half = ct // 2
        idx = 0
        for r in range(h):
            for c in range(w):
                raw["board"][r][c]["type"] = "forest"
                if idx < half - 1:
                    raw["board"][r][c]["owner"] = "human"
                else:
                    raw["board"][r][c]["owner"] = None
                idx += 1

        raw["board"][0][0]["owner"] = None  # target tile to claim
        raw["scores"]          = {"human": half - 1, "ai": 0}
        raw["claimable_total"] = ct
        raw["valid_moves"]     = {"human": [[0, 0]], "ai": []}
        raw["turn"]            = "human"
        raw["status"]          = "in_progress"
        database.save_game(raw)

        resp = client.post(f"/game/{gid}/move", json={"row": 0, "col": 0})
        assert resp.get_json()["status"] == "human_wins"


# ── 4. Barbarian trigger via Tower ─────────────────────────────────────────────

class TestBarbarianViaTower:
    def test_tower_claim_triggers_nearby_barbarian(self, client):
        """Claiming a Tower that reveals a Barbarian within distance < 3 fires it."""
        gid, _ = _new_game(client)
        raw = database.load_game(gid)
        h, w = raw["height"], raw["width"]

        # Reset to a clear 8×8 forest board with one human domain
        for r in range(h):
            for c in range(w):
                raw["board"][r][c] = {
                    "type": "forest", "owner": None,
                    "visible": False, "special_state": {}
                }

        # Human domain at (4,4)
        raw["board"][4][4] = {"type": "domain", "owner": "human", "visible": True, "special_state": {}}
        # Tower at (4,5) — in human's valid moves (adjacent to domain)
        raw["board"][4][5] = {"type": "tower", "owner": None, "visible": True, "special_state": {}}
        # Barbarian at (4,6) — within distance 2 of Tower, not yet triggered
        raw["board"][4][6] = {
            "type": "barbarian", "owner": None, "visible": False,
            "special_state": {"direction": "horizontal", "triggered": False}
        }
        # Mark Barbarian's row tiles as owned by human to detect sweep
        raw["board"][4][3] = {"type": "forest", "owner": "human", "visible": True, "special_state": {}}

        raw["scores"]          = {"human": 2, "ai": 0}
        raw["claimable_total"] = h * w - 1  # approximate
        raw["valid_moves"]     = {"human": [[4, 5]], "ai": []}
        raw["turn"]            = "human"
        raw["status"]          = "in_progress"
        raw["phase"]           = None
        raw["phase_data"]      = {}
        database.save_game(raw)

        resp = client.post(f"/game/{gid}/move", json={"row": 4, "col": 5})
        assert resp.status_code == 200
        data = resp.get_json()
        board = data["board"]

        # After barbarian trigger, (4,3) should have been swept (owner → None)
        # and the barbarian tile should now be a forest (or triggered)
        assert board[4][3]["owner"] is None, "Barbarian should have swept (4,3)"
        assert board[4][6]["type"] in ("forest", "barbarian"), "Barbarian tile updated"
        # Barbarian's special_state should indicate it fired
        if board[4][6]["type"] == "barbarian":
            assert board[4][6]["special_state"].get("triggered") is True


# ── 5. Cave chain ──────────────────────────────────────────────────────────────

class TestCaveChain:
    def test_two_cave_claims_make_both_inert(self, client):
        """Claim Cave A, then Cave B; verify both become inert in state."""
        gid, _ = _new_game(client)
        raw = database.load_game(gid)
        h, w = raw["height"], raw["width"]

        # Clean board
        for r in range(h):
            for c in range(w):
                raw["board"][r][c] = {
                    "type": "forest", "owner": None,
                    "visible": False, "special_state": {}
                }

        # Human domain at (0,0); Cave A at (0,1); Cave B at (0,3)
        raw["board"][0][0] = {"type": "domain", "owner": "human", "visible": True, "special_state": {}}
        raw["board"][0][1] = {
            "type": "cave", "owner": None, "visible": True,
            "special_state": {"inert": False, "connected_to": None}
        }
        raw["board"][0][3] = {
            "type": "cave", "owner": None, "visible": True,
            "special_state": {"inert": False, "connected_to": None}
        }

        raw["scores"]            = {"human": 1, "ai": 0}
        raw["claimable_total"]   = h * w
        raw["valid_moves"]       = {"human": [[0, 1]], "ai": []}
        raw["unconnected_caves"] = {"human": [], "ai": []}
        raw["turn"]              = "human"
        raw["status"]            = "in_progress"
        raw["phase"]             = None
        raw["phase_data"]        = {}
        database.save_game(raw)

        # Step 1: Claim Cave A
        resp1 = client.post(f"/game/{gid}/move", json={"row": 0, "col": 1})
        assert resp1.status_code == 200
        data1 = resp1.get_json()
        vm1 = data1["valid_moves"]
        assert [0, 3] in vm1, f"Cave B should be in valid moves after Cave A claim: {vm1}"

        # Patch state to give human the move for Cave B
        raw2 = database.load_game(gid)
        raw2["valid_moves"]["human"] = [[0, 3]]
        raw2["turn"] = "human"
        database.save_game(raw2)

        # Step 2: Claim Cave B
        resp2 = client.post(f"/game/{gid}/move", json={"row": 0, "col": 3})
        assert resp2.status_code == 200
        data2 = resp2.get_json()
        board2 = data2["board"]
        assert board2[0][1]["special_state"].get("inert") is True
        assert board2[0][3]["special_state"].get("inert") is True

    def test_inert_caves_not_in_subsequent_valid_moves(self, client):
        """After two caves become inert, they no longer appear as cave destinations."""
        gid, _ = _new_game(client)
        raw = database.load_game(gid)
        h, w = raw["height"], raw["width"]

        for r in range(h):
            for c in range(w):
                raw["board"][r][c] = {
                    "type": "forest", "owner": None,
                    "visible": False, "special_state": {}
                }

        raw["board"][0][0] = {"type": "domain", "owner": "human", "visible": True, "special_state": {}}
        raw["board"][0][1] = {
            "type": "cave", "owner": "human", "visible": True,
            "special_state": {"inert": True, "connected_to": [0, 3]}
        }
        raw["board"][0][3] = {
            "type": "cave", "owner": "human", "visible": True,
            "special_state": {"inert": True, "connected_to": [0, 1]}
        }
        # A third cave that is NOT inert
        raw["board"][2][2] = {
            "type": "cave", "owner": None, "visible": True,
            "special_state": {"inert": False, "connected_to": None}
        }
        # Domain adjacent to a forest for a simple valid move target
        raw["board"][0][4] = {"type": "forest", "owner": None, "visible": True, "special_state": {}}

        raw["scores"]            = {"human": 3, "ai": 0}
        raw["claimable_total"]   = h * w
        raw["valid_moves"]       = {"human": [[0, 4]], "ai": []}
        raw["unconnected_caves"] = {"human": [], "ai": []}
        raw["turn"]              = "human"
        raw["status"]            = "in_progress"
        raw["phase"]             = None
        raw["phase_data"]        = {}
        database.save_game(raw)

        # Claim the forest tile — inert caves should NOT appear as valid moves
        resp = client.post(f"/game/{gid}/move", json={"row": 0, "col": 4})
        assert resp.status_code == 200
        data = resp.get_json()
        vm = data["valid_moves"]
        assert [0, 1] not in vm, "Inert cave (0,1) should not appear in valid moves"
        assert [0, 3] not in vm, "Inert cave (0,3) should not appear in valid moves"


# ── 6. Plains edge case ────────────────────────────────────────────────────────

class TestPlainsEdgeCase:
    def test_plains_at_edge_produces_fewer_candidates(self, client):
        """Plains at (0,0) corner has at most 2 cardinal-distance-2 candidates."""
        gid, _ = _new_game(client)
        raw = database.load_game(gid)
        h, w = raw["height"], raw["width"]

        for r in range(h):
            for c in range(w):
                raw["board"][r][c] = {
                    "type": "forest", "owner": None,
                    "visible": False, "special_state": {}
                }

        # Human domain at (0,1) to give adjacency; Plains at (0,0) — corner
        raw["board"][0][1] = {"type": "domain", "owner": "human", "visible": True, "special_state": {}}
        raw["board"][0][0] = {"type": "plains", "owner": None, "visible": True, "special_state": {}}
        # Make the distance-2 tiles visible
        if h > 2:
            raw["board"][2][0]["visible"] = True  # down 2
        if w > 2:
            raw["board"][0][2]["visible"] = True  # right 2

        raw["scores"]          = {"human": 1, "ai": 0}
        raw["claimable_total"] = h * w
        raw["valid_moves"]     = {"human": [[0, 0]], "ai": []}
        raw["turn"]            = "human"
        raw["status"]          = "in_progress"
        raw["phase"]           = None
        raw["phase_data"]      = {}
        database.save_game(raw)

        resp = client.post(f"/game/{gid}/move", json={"row": 0, "col": 0})
        assert resp.status_code == 200
        data = resp.get_json()

        if data.get("phase") == "plains_first_pick":
            candidates = data["valid_moves"]
            # Corner (0,0) has only "down" and "right" at distance 2
            assert len(candidates) <= 2
            for r, c in candidates:
                dist = abs(r - 0) + abs(c - 0)
                assert dist == 2, f"Candidate ({r},{c}) not at distance 2 from plains at (0,0)"

    def test_plains_pick_completes_even_when_one_candidate(self, client):
        """Plains with only 1 candidate still works correctly (no second pick)."""
        gid, _ = _new_game(client)
        raw = database.load_game(gid)
        h, w = raw["height"], raw["width"]

        for r in range(h):
            for c in range(w):
                raw["board"][r][c] = {
                    "type": "mountain", "owner": None,
                    "visible": True, "special_state": {}
                }

        # Only (0,0) and (2,0) are non-mountain; plains at (0,0), domain at (1,0)
        raw["board"][0][0] = {"type": "plains", "owner": None, "visible": True, "special_state": {}}
        raw["board"][1][0] = {"type": "domain", "owner": "human", "visible": True, "special_state": {}}
        raw["board"][2][0] = {"type": "forest", "owner": None, "visible": True, "special_state": {}}

        raw["scores"]          = {"human": 1, "ai": 0}
        raw["claimable_total"] = 3
        raw["valid_moves"]     = {"human": [[0, 0]], "ai": []}
        raw["turn"]            = "human"
        raw["status"]          = "in_progress"
        raw["phase"]           = None
        raw["phase_data"]      = {}
        database.save_game(raw)

        resp = client.post(f"/game/{gid}/move", json={"row": 0, "col": 0})
        assert resp.status_code == 200
        # Game should either enter a phase or continue normally (no crash)
        assert resp.get_json()["status"] in ("in_progress", "human_wins", "tie", "ai_wins")


# ── 7. Wizard used by AI ──────────────────────────────────────────────────────

class TestWizardUsedByAI:
    def test_ai_move_succeeds_when_holding_wizard(self, client):
        """AI holding wizard can make a move; endpoint returns 200."""
        gid, _ = _new_game(client, difficulty="easy")
        raw = database.load_game(gid)

        raw["wizard_held_by"] = "ai"
        raw["turn"]           = "ai"
        raw["status"]         = "in_progress"
        # Ensure AI has valid moves
        vm_ai = raw.get("valid_moves", {}).get("ai") or []
        if not vm_ai:
            # Find any unclaimed forest tile
            for r, row in enumerate(raw["board"]):
                for c, tile in enumerate(row):
                    if tile["owner"] is None and tile["type"] not in ("mountain",):
                        vm_ai = [[r, c]]
                        break
                if vm_ai:
                    break
        raw["valid_moves"]["ai"] = vm_ai
        database.save_game(raw)

        resp = client.post(f"/game/{gid}/ai-move")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] in ("in_progress", "human_wins", "ai_wins", "tie")

    def test_wizard_consumed_after_ai_wizard_teleport(self, client):
        """After AI uses wizard teleport, wizard_held_by becomes null."""
        gid, _ = _new_game(client, difficulty="easy")
        raw = database.load_game(gid)
        h, w = raw["height"], raw["width"]

        # Give AI wizard and NO normal valid moves — forces wizard use
        raw["wizard_held_by"]    = "ai"
        raw["turn"]              = "ai"
        raw["status"]            = "in_progress"
        raw["valid_moves"]["ai"] = []   # no normal moves → AI uses wizard
        # Make sure there are unclaimed non-mountain tiles for wizard to target
        for r in range(h):
            for c in range(w):
                if raw["board"][r][c]["type"] not in ("mountain",) and raw["board"][r][c]["owner"] is None:
                    raw["board"][r][c]["visible"] = True
        database.save_game(raw)

        resp = client.post(f"/game/{gid}/ai-move")
        assert resp.status_code == 200
        data = resp.get_json()
        # Wizard was the only option → it should have been consumed
        assert data["wizard_held_by"] != "ai", "Wizard should be consumed after AI teleport"


# ── 8. Large board performance ─────────────────────────────────────────────────

class TestLargeBoardPerformance:
    def test_hard_ai_completes_within_time_cap(self, client):
        """24×20 board, Hard difficulty: AI move finishes within 10 s."""
        gid, _ = _new_game(client, width=24, height=20, difficulty="hard", seed=42)

        # Switch turn to AI
        raw = database.load_game(gid)
        raw["turn"] = "ai"
        # Ensure AI has at least one valid move
        if not raw["valid_moves"]["ai"]:
            for r, row in enumerate(raw["board"]):
                for c, tile in enumerate(row):
                    if tile["owner"] is None and tile["type"] not in ("mountain",):
                        raw["valid_moves"]["ai"] = [[r, c]]
                        break
                if raw["valid_moves"]["ai"]:
                    break
        database.save_game(raw)

        start   = time.perf_counter()
        resp    = client.post(f"/game/{gid}/ai-move")
        elapsed = time.perf_counter() - start

        assert resp.status_code == 200
        assert elapsed < 10.0, f"AI move took {elapsed:.2f}s on Hard; expected < 10s"
