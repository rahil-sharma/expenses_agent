from __future__ import annotations

import asyncio
from typing import Protocol


class IdempotencyStore(Protocol):
    async def get(self, key: str) -> str | None: ...

    async def put(self, key: str, response: str) -> None: ...


class InMemoryIdempotencyStore:
    def __init__(self) -> None:
        self._responses: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> str | None:
        async with self._lock:
            return self._responses.get(key)

    async def put(self, key: str, response: str) -> None:
        async with self._lock:
            self._responses[key] = response
