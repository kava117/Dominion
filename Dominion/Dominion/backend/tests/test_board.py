"""Stage 1 tests — board generation."""
import pytest
from game.board import (
    generate_board,
    T_MOUNTAIN, T_WIZARD, T_CAVE, T_BARBARIAN, T_DOMAIN, T_FOREST,
)


def tile_count(board, tile_type):
    return sum(1 for row in board for t in row if t["type"] == tile_type)


# ---------------------------------------------------------------------------
# Seed determinism
# ---------------------------------------------------------------------------
class TestSeedDeterminism:
    def test_same_seed_produces_same_board(self):
        b1, _ = generate_board(12, 10, seed=42)
        b2, _ = generate_board(12, 10, seed=42)
        assert b1 == b2

    def test_different_seeds_produce_different_boards(self):
        b1, _ = generate_board(12, 10, seed=1)
        b2, _ = generate_board(12, 10, seed=2)
        types1 = [[t["type"] for t in row] for row in b1]
        types2 = [[t["type"] for t in row] for row in b2]
        assert types1 != types2

    def test_various_seeds_all_deterministic(self):
        for seed in (0, 100, 999, 2**16, 2**32 - 1):
            b1, _ = generate_board(12, 10, seed=seed)
            b2, _ = generate_board(12, 10, seed=seed)
            assert b1 == b2, f"Non-deterministic for seed {seed}"


# ---------------------------------------------------------------------------
# Board dimensions
# ---------------------------------------------------------------------------
class TestBoardDimensions:
    @pytest.mark.parametrize("w,h", [(12, 10), (6, 6), (24, 20), (8, 15)])
    def test_correct_dimensions(self, w, h):
        board, _ = generate_board(w, h, seed=99)
        assert len(board) == h
        assert all(len(row) == w for row in board)


# ---------------------------------------------------------------------------
# Mountain count
# ---------------------------------------------------------------------------
class TestMountains:
    @pytest.mark.parametrize("seed", range(10))
    def test_mountain_count_in_range(self, seed):
        board, meta = generate_board(12, 10, seed=seed)
        total = 12 * 10
        # Allow slight rounding tolerance
        assert 0.09 * total <= meta["n_mountains"] <= 0.21 * total, (
            f"Mountain count {meta['n_mountains']} out of [9%,21%] range for seed {seed}"
        )

    def test_mountains_always_visible(self):
        board, _ = generate_board(12, 10, seed=7)
        for row in board:
            for tile in row:
                if tile["type"] == T_MOUNTAIN:
                    assert tile["visible"] is True

    def test_mountains_have_no_owner(self):
        board, _ = generate_board(12, 10, seed=7)
        for row in board:
            for tile in row:
                if tile["type"] == T_MOUNTAIN:
                    assert tile["owner"] is None


# ---------------------------------------------------------------------------
# Wizard
# ---------------------------------------------------------------------------
class TestWizard:
    @pytest.mark.parametrize("seed", range(10))
    def test_exactly_one_wizard(self, seed):
        board, meta = generate_board(12, 10, seed=seed)
        assert meta["n_wizard"] == 1
        assert tile_count(board, T_WIZARD) == 1

    def test_wizard_always_visible(self):
        for seed in range(10):
            board, _ = generate_board(12, 10, seed=seed)
            for row in board:
                for tile in row:
                    if tile["type"] == T_WIZARD:
                        assert tile["visible"] is True, f"Wizard not visible (seed={seed})"

    def test_wizard_not_owned_initially(self):
        board, _ = generate_board(12, 10, seed=3)
        for row in board:
            for tile in row:
                if tile["type"] == T_WIZARD:
                    assert tile["owner"] is None


# ---------------------------------------------------------------------------
# Caves
# ---------------------------------------------------------------------------
class TestCaves:
    @pytest.mark.parametrize("seed", range(10))
    def test_caves_even_and_at_least_two(self, seed):
        board, _ = generate_board(12, 10, seed=seed)
        n = tile_count(board, T_CAVE)
        assert n >= 2, f"Only {n} cave(s) for seed {seed}"
        assert n % 2 == 0, f"Odd cave count {n} for seed {seed}"

    def test_caves_start_not_inert(self):
        board, _ = generate_board(12, 10, seed=5)
        for row in board:
            for tile in row:
                if tile["type"] == T_CAVE:
                    assert tile["special_state"]["inert"] is False


# ---------------------------------------------------------------------------
# Barbarians
# ---------------------------------------------------------------------------
class TestBarbarians:
    @pytest.mark.parametrize("seed", range(10))
    def test_at_least_one_barbarian(self, seed):
        board, meta = generate_board(12, 10, seed=seed)
        assert meta["n_barbarians"] >= 1

    def test_barbarians_have_triggered_false(self):
        # Direction is chosen at trigger time (spec §5.7), not seeded at board generation.
        for seed in range(10):
            board, _ = generate_board(12, 10, seed=seed)
            for row in board:
                for tile in row:
                    if tile["type"] == T_BARBARIAN:
                        assert "direction" not in tile["special_state"]
                        assert tile["special_state"]["triggered"] is False


# ---------------------------------------------------------------------------
# Domain tiles
# ---------------------------------------------------------------------------
class TestDomainTiles:
    @pytest.mark.parametrize("seed", range(20))
    def test_domain_tiles_not_on_mountain_or_special(self, seed):
        FORBIDDEN = {T_MOUNTAIN, "wizard", "cave", "tower", "plains", "barbarian"}
        board, _ = generate_board(12, 10, seed=seed, domain_tiles_per_player=2)
        for row in board:
            for tile in row:
                if tile["type"] == T_DOMAIN:
                    assert tile["type"] not in FORBIDDEN

    @pytest.mark.parametrize("seed", range(20))
    def test_domain_tiles_not_adjacent_to_each_other(self, seed):
        board, _ = generate_board(12, 10, seed=seed, domain_tiles_per_player=2)
        domain_pos = [
            (r, c)
            for r, row in enumerate(board)
            for c, tile in enumerate(row)
            if tile["type"] == T_DOMAIN
        ]
        for i, (r1, c1) in enumerate(domain_pos):
            for j, (r2, c2) in enumerate(domain_pos):
                if i != j:
                    assert abs(r1 - r2) + abs(c1 - c2) != 1, (
                        f"Domain tiles ({r1},{c1}) and ({r2},{c2}) are adjacent (seed={seed})"
                    )

    def test_correct_owner_counts(self):
        board, _ = generate_board(12, 10, seed=42, domain_tiles_per_player=2)
        human_count = sum(1 for row in board for t in row if t["type"] == T_DOMAIN and t["owner"] == "human")
        ai_count    = sum(1 for row in board for t in row if t["type"] == T_DOMAIN and t["owner"] == "ai")
        assert human_count == 2
        assert ai_count == 2

    def test_domain_tiles_are_visible(self):
        board, _ = generate_board(12, 10, seed=42)
        for row in board:
            for tile in row:
                if tile["type"] == T_DOMAIN:
                    assert tile["visible"] is True


# ---------------------------------------------------------------------------
# Metadata correctness
# ---------------------------------------------------------------------------
class TestMetadata:
    def test_metadata_counts_match_board(self):
        board, meta = generate_board(12, 10, seed=77)
        assert tile_count(board, T_MOUNTAIN) == meta["n_mountains"]
        assert tile_count(board, T_WIZARD)   == meta["n_wizard"]
        assert tile_count(board, T_CAVE)     == meta["n_caves"]
        assert tile_count(board, T_BARBARIAN) == meta["n_barbarians"]
        assert tile_count(board, T_DOMAIN)   == meta["n_domain"]
