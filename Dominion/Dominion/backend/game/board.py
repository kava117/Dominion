from __future__ import annotations
from seed import SeededRNG

# Tile type constants
T_FOREST    = "forest"
T_PLAINS    = "plains"
T_TOWER     = "tower"
T_CAVE      = "cave"
T_MOUNTAIN  = "mountain"
T_WIZARD    = "wizard"
T_BARBARIAN = "barbarian"
T_DOMAIN    = "domain"

CLAIMABLE_TYPES = {T_FOREST, T_PLAINS, T_TOWER, T_CAVE, T_WIZARD, T_BARBARIAN, T_DOMAIN}
SPECIAL_TYPES   = {T_PLAINS, T_TOWER, T_CAVE, T_WIZARD, T_BARBARIAN}


def _make_tile(tile_type: str, owner=None, visible=False, special_state=None) -> dict:
    return {
        "type":          tile_type,
        "owner":         owner,
        "visible":       visible,
        "special_state": special_state or {},
    }


def _special_counts(total: int, rng: SeededRNG) -> dict:
    """Determine special tile counts scaled to board size.

    RNG call order matters for seed determinism — do not reorder.
    """
    n_barbarians = rng.randint(1, min(3, max(1, total // 50)))
    n_caves      = max(2, (total // 60) * 2)   # always even, min 2
    n_towers     = max(2, total // 50)
    n_plains     = max(3, total // 30)
    return {
        "wizard":    1,
        "barbarian": n_barbarians,
        "cave":      n_caves,
        "tower":     n_towers,
        "plains":    n_plains,
    }


def generate_board(
    width: int,
    height: int,
    seed: int,
    domain_tiles_per_player: int = 2,
) -> tuple[list[list[dict]], dict]:
    """Generate a board from a seed.

    Returns (board, metadata) where metadata contains actual tile counts.
    Same seed + dimensions always produces the same board.
    """
    rng   = SeededRNG(seed)
    total = width * height

    # --- Mountains (RNG call #1: uniform for fraction) ---
    mountain_fraction = rng.uniform(0.10, 0.20)
    n_mountains       = max(0, round(mountain_fraction * total))

    # Shuffle all positions deterministically (sorted first for consistency)
    all_positions = sorted((r, c) for r in range(height) for c in range(width))
    rng.shuffle(all_positions)

    mountain_set = set(all_positions[:n_mountains])
    non_mountain  = [p for p in all_positions if p not in mountain_set]

    # --- Special tile counts (RNG call #2: randint for barbarians) ---
    counts = _special_counts(total, rng)

    # Place specials sequentially from non_mountain pool
    specials: dict[tuple, dict] = {}
    idx = [0]

    def place(tile_type: str, n: int, make_state=None) -> int:
        placed = 0
        while placed < n and idx[0] < len(non_mountain):
            pos = non_mountain[idx[0]]
            idx[0] += 1
            if pos in specials:
                continue
            state = make_state() if make_state else {}
            specials[pos] = {"type": tile_type, "special_state": state}
            placed += 1
        return placed

    # Wizard (RNG: no extra calls)
    place(T_WIZARD, 1, lambda: {"used": False})

    # Barbarians (RNG call per group: choice for direction)
    def barb_state():
        return {"direction": rng.choice(["horizontal", "vertical"]), "triggered": False}

    actual_barbarians = place(T_BARBARIAN, counts["barbarian"], barb_state)

    # Caves, Towers, Plains (no extra RNG calls)
    actual_caves  = place(T_CAVE,    counts["cave"],  lambda: {"inert": False, "connected_to": None})
    actual_towers = place(T_TOWER,   counts["tower"])
    actual_plains = place(T_PLAINS,  counts["plains"])

    # --- Build grid ---
    board: list[list[dict]] = []
    for r in range(height):
        row = []
        for c in range(width):
            pos = (r, c)
            if pos in mountain_set:
                tile = _make_tile(T_MOUNTAIN, visible=True)
            elif pos in specials:
                info      = specials[pos]
                is_wizard = (info["type"] == T_WIZARD)
                tile = _make_tile(
                    info["type"],
                    visible=is_wizard,  # Wizard always visible; others start fogged
                    special_state=info["special_state"],
                )
            else:
                tile = _make_tile(T_FOREST)  # fogged by default
            row.append(tile)
        board.append(row)

    # --- Starting Domain tiles ---
    # Must not be on mountains or specials, not cardinally adjacent to any other domain tile.
    eligible = sorted(
        (r, c)
        for r in range(height)
        for c in range(width)
        if (r, c) not in mountain_set and (r, c) not in specials
    )
    rng.shuffle(eligible)

    domain_placed: list[tuple[tuple, str]] = []
    domain_set:    set[tuple]              = set()

    def cardinal_neighbors_set(pos: tuple) -> set:
        r, c = pos
        return {(r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)}

    for player in ("human", "ai"):
        placed = 0
        for pos in eligible:
            if placed >= domain_tiles_per_player:
                break
            if pos in domain_set:
                continue
            # Not cardinally adjacent to any already-placed domain tile
            if any(pos in cardinal_neighbors_set(dp) for dp, _ in domain_placed):
                continue
            domain_placed.append((pos, player))
            domain_set.add(pos)
            placed += 1

    for (r, c), player in domain_placed:
        board[r][c] = _make_tile(T_DOMAIN, owner=player, visible=True)

    metadata = {
        "n_mountains":  len(mountain_set),
        "n_wizard":     1 if any(v["type"] == T_WIZARD for v in specials.values()) else 0,
        "n_barbarians": actual_barbarians,
        "n_caves":      actual_caves,
        "n_towers":     actual_towers,
        "n_plains":     actual_plains,
        "n_domain":     len(domain_placed),
        "total":        total,
    }

    return board, metadata
