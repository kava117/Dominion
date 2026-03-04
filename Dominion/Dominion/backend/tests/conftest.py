"""Shared test helpers and fixtures."""
import pytest
from main import create_app
from game.state import GameState


# ---------------------------------------------------------------------------
# Flask test client fixture
# ---------------------------------------------------------------------------
@pytest.fixture
def client(tmp_path):
    db = str(tmp_path / "test_games.db")
    app = create_app(db_path=db)
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# Board / state builders
# ---------------------------------------------------------------------------
def make_tile(tile_type, owner=None, visible=False, special_state=None):
    return {
        "type":          tile_type,
        "owner":         owner,
        "visible":       visible,
        "special_state": special_state or {},
    }


def make_board(layout: list[list[str]]) -> list[list[dict]]:
    """Build a board from a 2D list of tile-type strings.

    Use lowercase initials in layout strings:
      "F"  -> forest    "P"  -> plains
      "T"  -> tower     "C"  -> cave
      "M"  -> mountain  "W"  -> wizard
      "B"  -> barbarian "D"  -> domain (unowned)
    Owner suffixes: "Dh" = domain owned by human, "Da" = domain owned by ai.
    """
    _type_map = {
        "F": "forest", "P": "plains", "T": "tower", "C": "cave",
        "M": "mountain", "W": "wizard", "B": "barbarian", "D": "domain",
    }
    board = []
    for row in layout:
        board_row = []
        for cell in row:
            owner = None
            code  = cell[0].upper()
            if len(cell) == 2:
                owner = "human" if cell[1].lower() == "h" else "ai"
            tile_type = _type_map[code]
            special   = {}
            if tile_type == "cave":
                special = {"inert": False, "connected_to": None}
            elif tile_type == "barbarian":
                special = {"direction": "horizontal", "triggered": False}
            elif tile_type == "wizard":
                special = {"used": False}
            visible = (owner is not None) or (tile_type in ("mountain", "wizard"))
            board_row.append(make_tile(tile_type, owner=owner, visible=visible, special_state=special))
        board.append(board_row)
    return board


def make_state(
    layout:       list[list[str]],
    turn:         str  = "human",
    valid_moves:  dict | None = None,
    scores:       dict | None = None,
) -> GameState:
    """Create a GameState from a layout grid for testing."""
    board  = make_board(layout)
    height = len(board)
    width  = len(board[0]) if board else 0

    n_mountains    = sum(1 for row in board for t in row if t["type"] == "mountain")
    claimable_total = height * width - n_mountains

    # Auto-compute scores from owned tiles if not provided
    if scores is None:
        scores = {"human": 0, "ai": 0}
        for row in board:
            for tile in row:
                if tile["owner"] in ("human", "ai"):
                    scores[tile["owner"]] += 1

    data = {
        "game_id":               "test-game",
        "board":                 board,
        "width":                 width,
        "height":                height,
        "seed":                  0,
        "difficulty":            "medium",
        "turn":                  turn,
        "status":                "in_progress",
        "scores":                scores,
        "valid_moves":           valid_moves or {"human": [], "ai": []},
        "revealed_extra":        [],
        "wizard_held_by":        None,
        "phase":                 None,
        "phase_data":            {},
        "unconnected_caves":     {"human": [], "ai": []},
        "claimable_total":       claimable_total,
        "domain_tiles_per_player": 2,
    }
    return GameState(data)
