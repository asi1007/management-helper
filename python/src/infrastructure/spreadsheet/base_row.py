from __future__ import annotations

from typing import Any, Callable


class BaseRow:
    def __init__(
        self,
        values: list[Any],
        column_index_resolver: Callable[[str], int],
        row_number: int,
    ) -> None:
        self._values = list(values)
        self._column_index_resolver = column_index_resolver
        self.row_number = row_number

    def get(self, column_name: str) -> Any:
        idx = self._column_index_resolver(column_name)
        v = self._values[idx]
        return v.strip() if isinstance(v, str) else v

    def __getitem__(self, index: int) -> Any:
        return self._values[index]

    def __setitem__(self, index: int, value: Any) -> None:
        self._values[index] = value

    def __len__(self) -> int:
        return len(self._values)
