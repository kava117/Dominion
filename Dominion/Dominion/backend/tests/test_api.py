"""Stage 1 tests — API endpoints."""
import pytest
from main import create_app


@pytest.fixture
def client(tmp_path):
    db = str(tmp_path / "test_games.db")
    app = create_app(db_path=db)
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# POST /game/new
# ---------------------------------------------------------------------------
class TestNewGame:
    def test_returns_201(self, client):
        resp = client.post("/game/new", json={})
        assert resp.status_code == 201

    def test_response_has_required_fields(self, client):
        resp = client.post("/game/new", json={"width": 12, "height": 10, "seed": 42})
        data = resp.get_json()
        for field in ("game_id", "board", "valid_moves", "scores", "turn", "status",
                      "wizard_held_by", "seed", "width", "height"):
            assert field in data, f"Missing field: {field}"

    def test_seed_echoed_in_response(self, client):
        resp = client.post("/game/new", json={"seed": 12345})
        assert resp.get_json()["seed"] == 12345

    def test_dimensions_echoed(self, client):
        resp = client.post("/game/new", json={"width": 8, "height": 7, "seed": 1})
        data = resp.get_json()
        assert data["width"] == 8
        assert data["height"] == 7

    def test_board_matches_dimensions(self, client):
        resp = client.post("/game/new", json={"width": 8, "height": 7, "seed": 1})
        board = resp.get_json()["board"]
        assert len(board) == 7
        assert all(len(row) == 8 for row in board)

    def test_same_seed_produces_same_board(self, client):
        r1 = client.post("/game/new", json={"width": 12, "height": 10, "seed": 777})
        r2 = client.post("/game/new", json={"width": 12, "height": 10, "seed": 777})
        types1 = [[t["type"] for t in row] for row in r1.get_json()["board"]]
        types2 = [[t["type"] for t in row] for row in r2.get_json()["board"]]
        assert types1 == types2

    def test_initial_turn_is_human(self, client):
        resp = client.post("/game/new", json={})
        assert resp.get_json()["turn"] == "human"

    def test_status_is_in_progress(self, client):
        resp = client.post("/game/new", json={})
        assert resp.get_json()["status"] == "in_progress"

    def test_scores_start_non_negative(self, client):
        resp = client.post("/game/new", json={"seed": 42})
        scores = resp.get_json()["scores"]
        assert scores["human"] >= 0
        assert scores["ai"] >= 0

    def test_initial_valid_moves_non_empty(self, client):
        resp = client.post("/game/new", json={"seed": 42})
        vm = resp.get_json()["valid_moves"]
        assert len(vm) > 0, "Human should have valid moves from starting domain tiles"

    def test_valid_moves_are_not_mountains_or_claimed(self, client):
        resp = client.post("/game/new", json={"seed": 42})
        data = resp.get_json()
        board = data["board"]
        for r, c in data["valid_moves"]:
            tile = board[r][c]
            assert tile["type"] != "mountain", f"Valid move at ({r},{c}) is a mountain"
            assert tile["owner"] is None, f"Valid move at ({r},{c}) is already owned"

    # Validation errors
    def test_width_too_small(self, client):
        assert client.post("/game/new", json={"width": 3}).status_code == 400

    def test_width_too_large(self, client):
        assert client.post("/game/new", json={"width": 25}).status_code == 400

    def test_height_too_small(self, client):
        assert client.post("/game/new", json={"height": 5}).status_code == 400

    def test_height_too_large(self, client):
        assert client.post("/game/new", json={"height": 21}).status_code == 400

    def test_invalid_difficulty(self, client):
        assert client.post("/game/new", json={"difficulty": "godmode"}).status_code == 400

    def test_invalid_first_player(self, client):
        assert client.post("/game/new", json={"first_player": "robot"}).status_code == 400


# ---------------------------------------------------------------------------
# GET /game/<id>
# ---------------------------------------------------------------------------
class TestGetGame:
    def test_returns_200(self, client):
        game_id = client.post("/game/new", json={"seed": 1}).get_json()["game_id"]
        assert client.get(f"/game/{game_id}").status_code == 200

    def test_returns_same_game_id(self, client):
        game_id = client.post("/game/new", json={"seed": 1}).get_json()["game_id"]
        data = client.get(f"/game/{game_id}").get_json()
        assert data["game_id"] == game_id

    def test_nonexistent_game_returns_404(self, client):
        assert client.get("/game/does-not-exist").status_code == 404

    def test_board_tiles_have_required_fields(self, client):
        game_id = client.post("/game/new", json={"seed": 2}).get_json()["game_id"]
        board = client.get(f"/game/{game_id}").get_json()["board"]
        for row in board:
            for tile in row:
                for field in ("type", "owner", "visible"):
                    assert field in tile, f"Tile missing field: {field}"

    def test_wizard_always_visible_in_response(self, client):
        game_id = client.post("/game/new", json={"seed": 3}).get_json()["game_id"]
        board = client.get(f"/game/{game_id}").get_json()["board"]
        wizard_tiles = [t for row in board for t in row if t["type"] == "wizard"]
        assert len(wizard_tiles) == 1
        assert wizard_tiles[0]["visible"] is True


# ---------------------------------------------------------------------------
# GET /game/<id>/valid-moves
# ---------------------------------------------------------------------------
class TestValidMoves:
    def test_returns_200(self, client):
        game_id = client.post("/game/new", json={"seed": 5}).get_json()["game_id"]
        assert client.get(f"/game/{game_id}/valid-moves").status_code == 200

    def test_response_shape(self, client):
        game_id = client.post("/game/new", json={"seed": 5}).get_json()["game_id"]
        data = client.get(f"/game/{game_id}/valid-moves").get_json()
        assert "player" in data
        assert "valid_moves" in data
        assert isinstance(data["valid_moves"], list)

    def test_player_matches_current_turn(self, client):
        resp = client.post("/game/new", json={"seed": 5})
        game_id = resp.get_json()["game_id"]
        turn = resp.get_json()["turn"]
        vm_player = client.get(f"/game/{game_id}/valid-moves").get_json()["player"]
        assert vm_player == turn

    def test_nonexistent_game_returns_404(self, client):
        assert client.get("/game/nope/valid-moves").status_code == 404
