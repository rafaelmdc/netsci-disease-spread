"""A tiny generic registry — the project's one factory mechanism.

Used for models, strategies and layer builders so that adding any of them
is a single decorated function/class, with no central if/elif to edit and
no import cycles. Registration happens at import time; package ``__init__``
modules import their implementations to populate the registry.
"""

from __future__ import annotations

from collections.abc import Callable


class Registry[K, V]:
    def __init__(self, name: str) -> None:
        self.name = name
        self._items: dict[K, V] = {}

    def register(self, key: K) -> Callable[[V], V]:
        """Decorator: register an object under ``key`` and return it unchanged."""

        def decorator(obj: V) -> V:
            if key in self._items:
                raise ValueError(f"{self.name}: {key!r} already registered")
            self._items[key] = obj
            return obj

        return decorator

    def get(self, key: K) -> V:
        if key not in self._items:
            raise NotImplementedError(
                f"{self.name}: {key!r} not registered. available: {self.keys()}"
            )
        return self._items[key]

    def keys(self) -> list[K]:
        return list(self._items)

    def __contains__(self, key: object) -> bool:
        return key in self._items
