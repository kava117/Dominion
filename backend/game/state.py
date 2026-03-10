from game.board import generate_board, DOMAIN


class GameState:
    """Authoritative game state. All mutation happens through rules.py."""

    def __init__(self, config):
        self.config = config
        self.width = config["width"]
        self.height = config["height"]
        self.seed = config["seed"]
        self.difficulty = config.get("difficulty", "medium")
        self.domain_tiles_per_player = config.get("domain_tiles_per_player", 2)

        self.board, human_starts, ai_starts = generate_board(
            self.width, self.height, self.seed, self.domain_tiles_per_player
        )

        self.turn = "human"
        self.status = "in_progress"
        self.wizard_held_by = None
        self.wizard_used = {"human": False, "ai": False}

        # valid_moves[player][(r, c)] = {
        #   "non_cave": bool,            True if any non-cave tile contributed this move
        #   "cave_sources": [(r, c), ...]  specific cave tiles that contributed this move
        # }
        self.valid_moves = {"human": {}, "ai": {}}

        # Initialise valid moves from starting domain tiles
        from game.effects import add_tile_valid_moves
        for pos in human_starts:
            add_tile_valid_moves(self, pos[0], pos[1], "human")
        for pos in ai_starts:
            add_tile_valid_moves(self, pos[0], pos[1], "ai")

        self._update_scores()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def in_bounds(self, r, c):
        return 0 <= r < self.height and 0 <= c < self.width

    def tile(self, r, c):
        return self.board[r][c]

    def _update_scores(self):
        self.scores = {"human": 0, "ai": 0}
        for r in range(self.height):
            for c in range(self.width):
                owner = self.board[r][c]["owner"]
                if owner in self.scores:
                    self.scores[owner] += 1

    # ------------------------------------------------------------------
    # Clone (used by minimax)
    # ------------------------------------------------------------------

    def clone(self):
        new = object.__new__(GameState)
        new.config = self.config
        new.width = self.width
        new.height = self.height
        new.seed = self.seed
        new.difficulty = self.difficulty
        new.domain_tiles_per_player = self.domain_tiles_per_player

        # Deep copy board (list of list of dict)
        new.board = [[dict(cell) for cell in row] for row in self.board]

        new.turn = self.turn
        new.status = self.status
        new.wizard_held_by = self.wizard_held_by
        new.wizard_used = dict(self.wizard_used)
        new.scores = dict(self.scores)

        # Deep copy valid_moves
        new.valid_moves = {}
        for player in ("human", "ai"):
            new.valid_moves[player] = {}
            for (r, c), entry in self.valid_moves[player].items():
                new.valid_moves[player][(r, c)] = {
                    "non_cave": entry["non_cave"],
                    "cave_sources": list(entry["cave_sources"]),
                }
        return new

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self):
        """Return JSON-serialisable representation."""
        board_data = []
        for r in range(self.height):
            row = []
            for c in range(self.width):
                cell = self.board[r][c]
                row.append({
                    "type": cell["type"],
                    "owner": cell["owner"],
                    "visible": cell["visible"],
                    "inert": cell["inert"],
                })
            board_data.append(row)

        valid_moves = [[r, c] for (r, c) in self.valid_moves.get(self.turn, {})]

        return {
            "board": board_data,
            "valid_moves": valid_moves,
            "scores": self.scores,
            "turn": self.turn,
            "status": self.status,
            "wizard_held_by": self.wizard_held_by,
            "wizard_available": (
                self.wizard_held_by == self.turn
                and not self.wizard_used.get(self.turn, False)
            ),
            "seed": self.seed,
            "width": self.width,
            "height": self.height,
            "difficulty": self.difficulty,
        }
