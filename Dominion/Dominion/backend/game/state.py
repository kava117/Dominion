from __future__ import annotations
import uuid
import random
from typing import Optional

from game.board import generate_board, T_MOUNTAIN, T_DOMAIN
from game.rules import compute_initial_valid_moves, compute_visible


class GameState:
    """Full game state. Serialises to/from a plain dict for JSON and SQLite storage."""

    def __init__(self, data: dict):
        self._data = data

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------
    @property
    def data(self) -> dict:
        return self._data

    @property
    def game_id(self) -> str:
        return self._data["game_id"]

    @property
    def board(self) -> list:
        return self._data["board"]

    @property
    def turn(self) -> str:
        return self._data["turn"]

    @property
    def status(self) -> str:
        return self._data["status"]

    @property
    def scores(self) -> dict:
        return self._data["scores"]

    @property
    def width(self) -> int:
        return self._data["width"]

    @property
    def height(self) -> int:
        return self._data["height"]

    @property
    def seed(self) -> int:
        return self._data["seed"]

    @property
    def difficulty(self) -> str:
        return self._data["difficulty"]

    @property
    def wizard_held_by(self) -> Optional[str]:
        return self._data.get("wizard_held_by")

    @property
    def phase(self) -> Optional[str]:
        return self._data.get("phase")

    @property
    def phase_data(self) -> dict:
        return self._data.get("phase_data", {})

    @property
    def valid_moves(self) -> dict:
        return self._data["valid_moves"]

    @property
    def unconnected_caves(self) -> dict:
        return self._data.setdefault("unconnected_caves", {"human": [], "ai": []})

    @property
    def claimable_total(self) -> int:
        return self._data["claimable_total"]

    def tile(self, r: int, c: int) -> dict:
        return self._data["board"][r][c]

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------
    def to_dict(self) -> dict:
        return dict(self._data)

    @classmethod
    def from_dict(cls, data: dict) -> "GameState":
        return cls(data)

    def to_api_response(self) -> dict:
        """Shape matching spec Section 12, augmented with phase info."""
        board_with_visibility = self._apply_visibility()
        current_player = self._data["turn"]

        # During Plains sub-move return the phase-specific picks, not the full pool
        if self.phase == "plains_pick":
            vm = self.phase_data.get("valid_picks", [])
        else:
            vm = self._data["valid_moves"].get(current_player, [])

        return {
            "game_id":        self.game_id,
            "board":          board_with_visibility,
            "valid_moves":    vm,
            "scores":         self.scores,
            "turn":           self.turn,
            "status":         self.status,
            "wizard_held_by": self.wizard_held_by,
            "seed":           self.seed,
            "width":          self.width,
            "height":         self.height,
            "phase":          self.phase,
            "phase_data":     self.phase_data,
        }

    def _apply_visibility(self) -> list:
        """Return a copy of the board with the `visible` field correctly set."""
        visible_set = compute_visible(self)
        result = []
        for r, row in enumerate(self.board):
            out_row = []
            for c, tile in enumerate(row):
                t = dict(tile)
                t["visible"] = (r, c) in visible_set
                out_row.append(t)
            result.append(out_row)
        return result


def create_game(
    width: int = 12,
    height: int = 10,
    seed: Optional[int] = None,
    difficulty: str = "medium",
    domain_tiles_per_player: int = 2,
    first_player: str = "human",
) -> GameState:
    """Create a new game and return an initial GameState."""
    if seed is None:
        seed = random.randint(0, 2**32 - 1)

    board, metadata = generate_board(width, height, seed, domain_tiles_per_player)
    valid_moves     = compute_initial_valid_moves(board, height, width)

    # Claimable total excludes Mountains
    claimable_total = metadata["total"] - metadata["n_mountains"]

    # Count starting domain tiles toward score
    scores = {"human": 0, "ai": 0}
    for r in range(height):
        for c in range(width):
            tile = board[r][c]
            if tile["type"] == T_DOMAIN and tile["owner"]:
                scores[tile["owner"]] += 1

    state_data = {
        "game_id":               str(uuid.uuid4()),
        "board":                 board,
        "width":                 width,
        "height":                height,
        "seed":                  seed,
        "difficulty":            difficulty,
        "turn":                  first_player,
        "status":                "in_progress",
        "scores":                scores,
        "valid_moves":           valid_moves,
        "revealed_extra":        [],   # positions fog-revealed by Tower (≤ 3) or Plains (≤ 2)
        "wizard_held_by":        None,
        "phase":                 None,
        "phase_data":            {},
        "unconnected_caves":     {"human": [], "ai": []},
        "claimable_total":       claimable_total,
        "domain_tiles_per_player": domain_tiles_per_player,
    }

    return GameState(state_data)
