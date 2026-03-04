from flask import Flask, jsonify, request, abort

import database
from game.state import create_game, GameState
from game.rules import validate_move, apply_move
from game.ai.minimax import get_best_move, apply_ai_move
from game.effects import (
    validate_plains_pick,
    apply_plains_first_pick,
    apply_plains_second_pick,
    validate_wizard_teleport,
    apply_wizard_teleport,
)


DIFFICULTY_TIMEOUTS = {"easy": 10.0, "medium": 10.0, "hard": 5.0}


def create_app(db_path: str | None = None) -> Flask:
    app = Flask(__name__)

    if db_path:
        database.set_db_path(db_path)
    database.init_db()

    # ------------------------------------------------------------------
    # POST /game/new — start a new game
    # ------------------------------------------------------------------
    @app.route("/game/new", methods=["POST"])
    def new_game():
        body = request.get_json(silent=True) or {}

        width                  = body.get("width", 12)
        height                 = body.get("height", 10)
        seed                   = body.get("seed", None)
        difficulty             = body.get("difficulty", "medium")
        domain_tiles_per_player = body.get("domain_tiles_per_player", 2)
        first_player           = body.get("first_player", "human")

        if not (6 <= width <= 24):
            abort(400, description="width must be between 6 and 24")
        if not (6 <= height <= 20):
            abort(400, description="height must be between 6 and 20")
        if difficulty not in ("easy", "medium", "hard"):
            abort(400, description="difficulty must be easy, medium, or hard")
        if first_player not in ("human", "ai"):
            abort(400, description="first_player must be human or ai")
        if not (1 <= domain_tiles_per_player <= 4):
            abort(400, description="domain_tiles_per_player must be between 1 and 4")

        state = create_game(
            width=width,
            height=height,
            seed=seed,
            difficulty=difficulty,
            domain_tiles_per_player=domain_tiles_per_player,
            first_player=first_player,
        )
        database.save_game(state.to_dict())
        return jsonify(state.to_api_response()), 201

    # ------------------------------------------------------------------
    # GET /game/<id> — retrieve game state
    # ------------------------------------------------------------------
    @app.route("/game/<game_id>", methods=["GET"])
    def get_game(game_id):
        data = database.load_game(game_id)
        if data is None:
            abort(404, description="Game not found")
        state = GameState.from_dict(data)
        return jsonify(state.to_api_response())

    # ------------------------------------------------------------------
    # GET /game/<id>/valid-moves — valid moves for the active player
    # ------------------------------------------------------------------
    @app.route("/game/<game_id>/valid-moves", methods=["GET"])
    def valid_moves(game_id):
        data = database.load_game(game_id)
        if data is None:
            abort(404, description="Game not found")
        state = GameState.from_dict(data)
        current = state.turn
        return jsonify({
            "player":      current,
            "valid_moves": state.valid_moves.get(current, []),
        })

    # ------------------------------------------------------------------
    # POST /game/<id>/move — submit a human (or AI) move
    # ------------------------------------------------------------------
    @app.route("/game/<game_id>/move", methods=["POST"])
    def submit_move(game_id):
        data = database.load_game(game_id)
        if data is None:
            abort(404, description="Game not found")

        state = GameState.from_dict(data)

        if state.status != "in_progress":
            abort(400, description="Game is not in progress")

        body = request.get_json(silent=True) or {}

        # --- Wizard teleport ---
        if body.get("wizard"):
            row = body.get("row")
            col = body.get("col")
            if row is None or col is None:
                abort(400, description="row and col are required for wizard teleport")
            try:
                row, col = int(row), int(col)
            except (TypeError, ValueError):
                abort(400, description="row and col must be integers")
            valid, reason = validate_wizard_teleport(state, row, col)
            if not valid:
                abort(400, description=reason)
            apply_wizard_teleport(state, row, col)
            database.save_game(state.to_dict())
            return jsonify(state.to_api_response())

        # --- Normal / Plains-phase move ---
        row = body.get("row")
        col = body.get("col")
        if row is None or col is None:
            abort(400, description="row and col are required")
        try:
            row, col = int(row), int(col)
        except (TypeError, ValueError):
            abort(400, description="row and col must be integers")

        phase = state.phase

        if phase is None:
            valid, reason = validate_move(state, row, col)
            if not valid:
                abort(400, description=reason)
            apply_move(state, row, col)

        elif phase == "plains_first_pick":
            valid, reason = validate_plains_pick(state, row, col)
            if not valid:
                abort(400, description=reason)
            apply_plains_first_pick(state, row, col)

        elif phase == "plains_second_pick":
            valid, reason = validate_plains_pick(state, row, col)
            if not valid:
                abort(400, description=reason)
            apply_plains_second_pick(state, row, col)

        else:
            abort(400, description=f"Unexpected game phase: {phase}")

        database.save_game(state.to_dict())
        return jsonify(state.to_api_response())

    # ------------------------------------------------------------------
    # POST /game/<id>/ai-move — trigger the AI to compute and apply its move
    # ------------------------------------------------------------------
    @app.route("/game/<game_id>/ai-move", methods=["POST"])
    def ai_move(game_id):
        data = database.load_game(game_id)
        if data is None:
            abort(404, description="Game not found")

        state = GameState.from_dict(data)

        if state.status != "in_progress":
            abort(400, description="Game is not in progress")
        if state.turn != "ai":
            abort(400, description="It is not the AI's turn")
        if state.phase is not None:
            abort(400, description="Cannot trigger AI during a sub-phase")

        timeout = DIFFICULTY_TIMEOUTS.get(state.difficulty, 10.0)
        move = get_best_move(state, timeout_seconds=timeout)
        if move is None:
            abort(400, description="AI has no valid moves")

        apply_ai_move(state, move)
        database.save_game(state.to_dict())
        return jsonify(state.to_api_response())

    # ------------------------------------------------------------------
    # Error handlers
    # ------------------------------------------------------------------
    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": str(e.description)}), 400

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": str(e.description)}), 404

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=5000)
