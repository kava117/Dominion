"""Flask REST API — Domain Expansion backend."""

import os
import random
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

import database
from game.rules import make_move, get_valid_moves, pass_turn, player_has_moves, InvalidMoveError
from game.ai.minimax import choose_move

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'frontend')

app = Flask(__name__, static_folder=None)
CORS(app)


# ---------------------------------------------------------------------------
# Frontend serving
# ---------------------------------------------------------------------------

@app.route('/')
def serve_index():
    return send_from_directory(FRONTEND_DIR, 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    # Only serve known frontend files; let /game/* fall through to API routes
    if filename.startswith('game/'):
        return app.make_response(('Not found', 404))
    return send_from_directory(FRONTEND_DIR, filename)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _err(msg, code=400):
    return jsonify({"error": msg}), code


def _game_or_404(game_id):
    state = database.get_game(game_id)
    if state is None:
        return None, (jsonify({"error": "Game not found"}), 404)
    return state, None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/game/new", methods=["POST"])
def new_game():
    data = request.get_json(silent=True) or {}

    try:
        width = int(data.get("width", 12))
        height = int(data.get("height", 10))
        seed = data.get("seed")
        if seed is None:
            seed = random.randint(0, 2**31 - 1)
        else:
            seed = int(seed)
        difficulty = data.get("difficulty", "medium")
        domain_tiles = int(data.get("domain_tiles_per_player", 2))
    except (ValueError, TypeError) as exc:
        return _err(f"Invalid configuration: {exc}")

    if not (6 <= width <= 24):
        return _err("width must be between 6 and 24")
    if not (6 <= height <= 20):
        return _err("height must be between 6 and 20")
    if difficulty not in ("easy", "medium", "hard"):
        return _err("difficulty must be easy, medium, or hard")

    config = {
        "width": width,
        "height": height,
        "seed": seed,
        "difficulty": difficulty,
        "domain_tiles_per_player": domain_tiles,
    }

    game_id, state = database.create_game(config)
    resp = state.to_dict()
    resp["game_id"] = game_id
    return jsonify(resp), 201


@app.route("/game/<game_id>", methods=["GET"])
def get_game(game_id):
    state, err = _game_or_404(game_id)
    if err:
        return err
    resp = state.to_dict()
    resp["game_id"] = game_id
    return jsonify(resp)


@app.route("/game/<game_id>/move", methods=["POST"])
def player_move(game_id):
    state, err = _game_or_404(game_id)
    if err:
        return err

    if state.status != "in_progress":
        return _err("Game is already over.")

    if state.turn != "human":
        return _err("It is not the human player's turn.")

    data = request.get_json(silent=True) or {}
    try:
        r = int(data["row"])
        c = int(data["col"])
    except (KeyError, ValueError, TypeError):
        return _err("Request must include integer 'row' and 'col'.")

    wizard = bool(data.get("wizard", False))

    try:
        events = make_move(state, r, c, wizard=wizard)
    except InvalidMoveError as exc:
        return _err(str(exc))

    resp = state.to_dict()
    resp["game_id"] = game_id
    resp["events"] = events
    return jsonify(resp)


@app.route("/game/<game_id>/ai-move", methods=["POST"])
def ai_move(game_id):
    state, err = _game_or_404(game_id)
    if err:
        return err

    if state.status != "in_progress":
        return _err("Game is already over.")

    if state.turn != "ai":
        return _err("It is not the AI player's turn.")

    force = request.args.get('force') == '1'
    move = choose_move(state, force=force)
    if move is None:
        return _err("AI has no available moves.")

    try:
        events = make_move(state, move["row"], move["col"], wizard=move.get("wizard", False))
    except InvalidMoveError as exc:
        # Shouldn't happen — minimax only generates legal moves
        return _err(f"AI generated an illegal move: {exc}", 500)

    resp = state.to_dict()
    resp["game_id"] = game_id
    resp["events"] = events
    resp["ai_move"] = {"row": move["row"], "col": move["col"], "wizard": move.get("wizard", False)}
    return jsonify(resp)


@app.route("/game/<game_id>/pass", methods=["POST"])
def pass_turn_route(game_id):
    state, err = _game_or_404(game_id)
    if err:
        return err
    if state.status != "in_progress":
        return _err("Game is already over.")
    if state.turn != "human":
        return _err("Pass is only available on the human player's turn.")
    if player_has_moves(state, "human"):
        return _err("Cannot pass when moves are available.")
    pass_turn(state)
    resp = state.to_dict()
    resp["game_id"] = game_id
    return jsonify(resp)


@app.route("/game/<game_id>/valid-moves", methods=["GET"])
def valid_moves(game_id):
    state, err = _game_or_404(game_id)
    if err:
        return err
    moves = get_valid_moves(state)
    return jsonify({"valid_moves": [[r, c] for r, c in moves], "turn": state.turn})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True, port=5000)
