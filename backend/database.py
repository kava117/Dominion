"""In-memory game store."""

import uuid

_games = {}


def create_game(config):
    from game.state import GameState
    game_id = str(uuid.uuid4())
    state = GameState(config)
    _games[game_id] = state
    return game_id, state


def get_game(game_id):
    return _games.get(game_id)


def delete_game(game_id):
    _games.pop(game_id, None)
