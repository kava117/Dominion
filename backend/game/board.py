import random

# Tile type constants
MOUNTAIN = "mountain"
FOREST = "forest"
PLAINS = "plains"
TOWER = "tower"
CAVE = "cave"
WIZARD = "wizard"
BARBARIAN = "barbarian"
DOMAIN = "domain"

# Sets for quick membership tests
CLAIMABLE = {FOREST, PLAINS, TOWER, CAVE, WIZARD, DOMAIN}
SPECIAL = {PLAINS, TOWER, CAVE, WIZARD, BARBARIAN}

# Priority order for move ordering (higher = more valuable)
TILE_PRIORITY = {WIZARD: 5, TOWER: 4, CAVE: 3, PLAINS: 2, DOMAIN: 1, FOREST: 1, BARBARIAN: 0, MOUNTAIN: 0}


def manhattan(r1, c1, r2, c2):
    return abs(r1 - r2) + abs(c1 - c2)


def generate_board(width, height, seed, domain_tiles_per_player=2):
    """Generate a board using seeded RNG.

    Returns:
        (board, human_starts, ai_starts)
        board: 2D list of tile dicts
        human_starts: list of (r, c) for human starting domain tiles
        ai_starts: list of (r, c) for AI starting domain tiles
    """
    rng = random.Random(seed)
    total = width * height

    # Scale factor relative to reference 12x10 board
    scale = total / 120.0

    # Mountains: 10–20% of tiles
    mountain_count = max(1, int(total * rng.uniform(0.10, 0.20)))

    # Special tile counts
    wizard_count = 1
    barbarian_count = rng.randint(1, 3)
    cave_count = max(2, round(rng.randint(1, 3) * scale) * 2)  # always even
    tower_count = max(1, round(rng.uniform(1, 2) * scale))
    plains_count = max(1, round(rng.uniform(2, 4) * scale))

    # Shuffle all positions
    positions = [(r, c) for r in range(height) for c in range(width)]
    rng.shuffle(positions)

    tile_types = {}
    idx = 0

    def place(tile_type, count):
        nonlocal idx
        for _ in range(count):
            if idx < len(positions):
                tile_types[positions[idx]] = tile_type
                idx += 1

    place(MOUNTAIN, mountain_count)
    place(WIZARD, wizard_count)
    place(BARBARIAN, barbarian_count)
    place(CAVE, cave_count)
    place(TOWER, tower_count)
    place(PLAINS, plains_count)

    # Remaining tiles are Forest
    for i in range(idx, len(positions)):
        tile_types[positions[i]] = FOREST

    # Place domain tiles: must be Forest, not adjacent to each other
    forest_positions = [p for p in positions if tile_types[p] == FOREST]
    rng.shuffle(forest_positions)

    domains = []
    for pos in forest_positions:
        r, c = pos
        if not any(abs(r - er) + abs(c - ec) <= 1 for er, ec in domains):
            domains.append(pos)
            if len(domains) == domain_tiles_per_player * 2:
                break

    human_starts = domains[:domain_tiles_per_player]
    ai_starts = domains[domain_tiles_per_player:domain_tiles_per_player * 2]

    # Build board array
    board = []
    for r in range(height):
        row = []
        for c in range(width):
            t = tile_types.get((r, c), FOREST)
            owner = None
            if (r, c) in human_starts:
                owner = "human"
                t = DOMAIN
            elif (r, c) in ai_starts:
                owner = "ai"
                t = DOMAIN

            # Wizard is always visible; claimed tiles start visible
            visible = (owner is not None) or (t == WIZARD)

            row.append({
                "type": t,
                "owner": owner,
                "visible": visible,
                "inert": False,
            })
        board.append(row)

    return board, human_starts, ai_starts
