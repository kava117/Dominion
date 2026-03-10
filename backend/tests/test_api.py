"""Integration tests for the Flask REST API."""

import json
import pytest


# ---------------------------------------------------------------------------
# POST /game/new
# ---------------------------------------------------------------------------

class TestNewGame:
    def test_creates_game_with_defaults(self, client):
        resp = client.post("/game/new", json={})
        assert resp.status_code == 201
        data = resp.get_json()
        assert "game_id" in data
        assert data["width"] == 12
        assert data["height"] == 10
        assert data["turn"] == "human"
        assert data["status"] == "in_progress"

    def test_creates_game_with_custom_config(self, client):
        resp = client.post("/game/new", json={
            "width": 8, "height": 8, "seed": 1234, "difficulty": "hard"
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["width"] == 8
        assert data["height"] == 8
        assert data["seed"] == 1234
        assert data["difficulty"] == "hard"

    def test_same_seed_produces_same_board(self, client):
        r1 = client.post("/game/new", json={"seed": 9999}).get_json()
        r2 = client.post("/game/new", json={"seed": 9999}).get_json()
        assert r1["board"] == r2["board"]

    def test_invalid_width_rejected(self, client):
        resp = client.post("/game/new", json={"width": 3})
        assert resp.status_code == 400

    def test_invalid_height_rejected(self, client):
        resp = client.post("/game/new", json={"height": 25})
        assert resp.status_code == 400

    def test_invalid_difficulty_rejected(self, client):
        resp = client.post("/game/new", json={"difficulty": "insane"})
        assert resp.status_code == 400

    def test_board_has_correct_dimensions(self, client):
        resp = client.post("/game/new", json={"width": 10, "height": 8}).get_json()
        assert len(resp["board"]) == 8
        assert all(len(row) == 10 for row in resp["board"])


# ---------------------------------------------------------------------------
# GET /game/<id>
# ---------------------------------------------------------------------------

class TestGetGame:
    def test_returns_game_state(self, client):
        game_id = client.post("/game/new", json={}).get_json()["game_id"]
        resp = client.get(f"/game/{game_id}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["game_id"] == game_id

    def test_404_for_unknown_game(self, client):
        resp = client.get("/game/nonexistent-id")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /game/<id>/move
# ---------------------------------------------------------------------------

class TestPlayerMove:
    def _new_game(self, client, **kwargs):
        data = {"seed": 42, "width": 8, "height": 6, **kwargs}
        return client.post("/game/new", json=data).get_json()

    def test_valid_move_accepted(self, client):
        game = self._new_game(client)
        game_id = game["game_id"]
        r, c = game["valid_moves"][0]
        resp = client.post(f"/game/{game_id}/move", json={"row": r, "col": c})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["board"][r][c]["owner"] == "human"
        assert data["turn"] == "ai"

    def test_invalid_move_rejected(self, client):
        game = self._new_game(client)
        game_id = game["game_id"]
        resp = client.post(f"/game/{game_id}/move", json={"row": 0, "col": 0})
        # Might be valid or invalid; if invalid should get 400
        # Pick a definitely invalid position: out of bounds
        resp = client.post(f"/game/{game_id}/move", json={"row": 999, "col": 999})
        assert resp.status_code == 400

    def test_wrong_turn_rejected(self, client):
        game = self._new_game(client)
        game_id = game["game_id"]
        # Make human's first move to switch turn to AI
        r, c = game["valid_moves"][0]
        client.post(f"/game/{game_id}/move", json={"row": r, "col": c})
        # Now it's AI's turn; human move should fail
        resp = client.post(f"/game/{game_id}/move", json={"row": r, "col": c})
        assert resp.status_code == 400

    def test_missing_row_col_rejected(self, client):
        game = self._new_game(client)
        game_id = game["game_id"]
        resp = client.post(f"/game/{game_id}/move", json={"row": 1})
        assert resp.status_code == 400

    def test_response_includes_events(self, client):
        game = self._new_game(client)
        game_id = game["game_id"]
        r, c = game["valid_moves"][0]
        data = client.post(f"/game/{game_id}/move", json={"row": r, "col": c}).get_json()
        assert "events" in data

    def test_score_updates_after_move(self, client):
        game = self._new_game(client)
        game_id = game["game_id"]
        initial_score = game["scores"]["human"]
        r, c = game["valid_moves"][0]
        data = client.post(f"/game/{game_id}/move", json={"row": r, "col": c}).get_json()
        assert data["scores"]["human"] == initial_score + 1


# ---------------------------------------------------------------------------
# POST /game/<id>/ai-move
# ---------------------------------------------------------------------------

class TestAIMove:
    def _game_on_ai_turn(self, client):
        game = client.post("/game/new", json={
            "seed": 7, "width": 8, "height": 6, "difficulty": "easy"
        }).get_json()
        game_id = game["game_id"]
        r, c = game["valid_moves"][0]
        client.post(f"/game/{game_id}/move", json={"row": r, "col": c})
        return game_id

    def test_ai_move_returns_200(self, client):
        game_id = self._game_on_ai_turn(client)
        resp = client.post(f"/game/{game_id}/ai-move")
        assert resp.status_code == 200

    def test_ai_move_claims_a_tile(self, client):
        game_id = self._game_on_ai_turn(client)
        data = client.post(f"/game/{game_id}/ai-move").get_json()
        move = data["ai_move"]
        assert data["board"][move["row"]][move["col"]]["owner"] == "ai"

    def test_ai_move_advances_turn(self, client):
        game_id = self._game_on_ai_turn(client)
        data = client.post(f"/game/{game_id}/ai-move").get_json()
        assert data["turn"] == "human"

    def test_ai_move_on_human_turn_rejected(self, client):
        game = client.post("/game/new", json={"seed": 1}).get_json()
        game_id = game["game_id"]
        resp = client.post(f"/game/{game_id}/ai-move")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /game/<id>/valid-moves
# ---------------------------------------------------------------------------

class TestValidMoves:
    def test_returns_valid_moves(self, client):
        game = client.post("/game/new", json={"seed": 5}).get_json()
        game_id = game["game_id"]
        resp = client.get(f"/game/{game_id}/valid-moves")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "valid_moves" in data
        assert "turn" in data
        assert isinstance(data["valid_moves"], list)

    def test_valid_moves_match_game_state(self, client):
        game = client.post("/game/new", json={"seed": 5}).get_json()
        game_id = game["game_id"]
        moves_resp = client.get(f"/game/{game_id}/valid-moves").get_json()
        state_vm = {tuple(m) for m in game["valid_moves"]}
        endpoint_vm = {tuple(m) for m in moves_resp["valid_moves"]}
        assert state_vm == endpoint_vm
