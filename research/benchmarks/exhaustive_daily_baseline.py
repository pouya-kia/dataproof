"""Tiny Phase 0 mathematical baseline for two one-order days.

This is a reference enumeration, not a SQL executor or a shipped verifier.
"""

from itertools import product


def daily_view(world: tuple[int, int]) -> tuple[tuple[int, int, int], ...]:
    return tuple((day, 1, 1) for day in (0, 1))


def monthly_distinct(world: tuple[int, int]) -> int:
    return len(set(world))


def main() -> None:
    worlds = list(product((1, 2), repeat=2))
    pairs = [
        (left, right)
        for left in worlds
        for right in worlds
        if daily_view(left) == daily_view(right)
        and monthly_distinct(left) != monthly_distinct(right)
    ]
    assert pairs
    left, right = pairs[0]
    print(f"worlds={len(worlds)} witness_pairs={len(pairs)}")
    print(f"D1={left} D2={right}")
    print(f"daily_equal={daily_view(left) == daily_view(right)}")
    print(f"monthly_distinct={monthly_distinct(left)},{monthly_distinct(right)}")


if __name__ == "__main__":
    main()
