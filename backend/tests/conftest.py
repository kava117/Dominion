"""Shared fixtures for the test suite."""

import pytest
from game.state import GameState
from main import app as flask_app


def make_state(width=8, height=6, seed=42, difficulty="medium", domain_tiles=1):
    """Return a fresh GameState with deterministic configuration."""
    return GameState({
        "width": width,
        "height": height,
        "seed": seed,
        "difficulty": difficulty,
        "domain_tiles_per_player": domain_tiles,
    })


@pytest.fixture
def state():
    return make_state()


@pytest.fixture
def client():
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as c:
        yield c
