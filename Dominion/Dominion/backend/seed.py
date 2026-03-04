import random as _random


class SeededRNG:
    """Deterministic RNG wrapper. Same seed always produces the same sequence."""

    def __init__(self, seed: int | None = None):
        if seed is None:
            seed = _random.randint(0, 2**32 - 1)
        self.seed = seed
        self._rng = _random.Random(seed)

    def randint(self, a: int, b: int) -> int:
        return self._rng.randint(a, b)

    def uniform(self, a: float, b: float) -> float:
        return self._rng.uniform(a, b)

    def shuffle(self, lst: list) -> list:
        self._rng.shuffle(lst)
        return lst

    def choice(self, seq):
        return self._rng.choice(seq)

    def sample(self, population, k: int) -> list:
        return self._rng.sample(population, k)
