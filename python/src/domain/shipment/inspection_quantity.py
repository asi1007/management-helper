from __future__ import annotations


def resolve_registered_quantity(*, instructed: int, good: int) -> int:
    if good < 0:
        raise ValueError(f"良品数量が不正です: {good}")
    return good


def allocate_good_quantity(instructed_per_row: list[int], good_total: int) -> list[int]:
    if not instructed_per_row:
        return []
    allocated: list[int] = []
    remaining = good_total
    for instructed in instructed_per_row[:-1]:
        assigned = min(instructed, max(remaining, 0))
        allocated.append(assigned)
        remaining -= assigned
    allocated.append(max(remaining, 0))
    return allocated
