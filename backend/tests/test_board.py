"""Tests for board generation."""

import pytest
from game.board import (
    generate_board, MOUNTAIN, FOREST, PLAINS, TOWER, CAVE, WIZARD,
    BARBARIAN, DOMAIN
)


def _flat(board):
    return [cell for row in board for cell in row]


def test_board_dimensions():
    board, _, _ = generate_board(12, 10, seed=1)
    assert len(board) == 10
    assert all(len(row) == 12 for row in board)


def test_board_deterministic():
    b1, h1, a1 = generate_board(12, 10, seed=99)
    b2, h2, a2 = generate_board(12, 10, seed=99)
    assert b1 == b2
    assert h1 == h2
    assert a1 == a2


def test_different_seeds_differ():
    b1, _, _ = generate_board(12, 10, seed=1)
    b2, _, _ = generate_board(12, 10, seed=2)
    types1 = [[c["type"] for c in row] for row in b1]
    types2 = [[c["type"] for c in row] for row in b2]
    assert types1 != types2


def test_exactly_one_wizard():
    board, _, _ = generate_board(12, 10, seed=7)
    wizards = [c for c in _flat(board) if c["type"] == WIZARD]
    assert len(wizards) == 1


def test_wizard_always_visible():
    board, _, _ = generate_board(12, 10, seed=7)
    for cell in _flat(board):
        if cell["type"] == WIZARD:
            assert cell["visible"] is True


def test_cave_count_even_and_at_least_two():
    for seed in range(10):
        board, _, _ = generate_board(12, 10, seed=seed)
        caves = [c for c in _flat(board) if c["type"] == CAVE]
        assert len(caves) >= 2
        assert len(caves) % 2 == 0, f"seed={seed}: cave count {len(caves)} is odd"


def test_mountain_count_in_range():
    board, _, _ = generate_board(12, 10, seed=3)
    total = 12 * 10
    mountains = sum(1 for c in _flat(board) if c["type"] == MOUNTAIN)
    assert total * 0.08 <= mountains <= total * 0.22, f"mountains={mountains}"


def test_domain_tiles_owned():
    board, human_starts, ai_starts = generate_board(12, 10, seed=5, domain_tiles_per_player=2)
    for r, c in human_starts:
        assert board[r][c]["owner"] == "human"
        assert board[r][c]["type"] == DOMAIN
    for r, c in ai_starts:
        assert board[r][c]["owner"] == "ai"
        assert board[r][c]["type"] == DOMAIN


def test_domain_tiles_not_adjacent():
    board, human_starts, ai_starts = generate_board(12, 10, seed=5, domain_tiles_per_player=2)
    all_domains = human_starts + ai_starts
    for i, (r1, c1) in enumerate(all_domains):
        for j, (r2, c2) in enumerate(all_domains):
            if i != j:
                dist = abs(r1 - r2) + abs(c1 - c2)
                assert dist > 1, f"Domains at {(r1,c1)} and {(r2,c2)} are adjacent"


def test_domain_tiles_visible():
    board, human_starts, ai_starts = generate_board(12, 10, seed=5)
    for r, c in human_starts + ai_starts:
        assert board[r][c]["visible"] is True


def test_no_unclaimed_mountains():
    board, _, _ = generate_board(10, 8, seed=11)
    for cell in _flat(board):
        if cell["type"] == MOUNTAIN:
            assert cell["owner"] is None


def test_barbarian_count_in_range():
    for seed in range(5):
        board, _, _ = generate_board(12, 10, seed=seed)
        barbs = [c for c in _flat(board) if c["type"] == BARBARIAN]
        assert 1 <= len(barbs) <= 3
