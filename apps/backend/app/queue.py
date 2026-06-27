"""Task queue abstraction.

Production: ArqTaskQueue wraps a real arq/Redis pool.
Tests: MemoryTaskQueue captures enqueued jobs in a list — no Redis needed.
"""

from __future__ import annotations

from typing import Any


class ArqTaskQueue:
    def __init__(self, pool: Any) -> None:
        self._pool = pool

    async def enqueue(self, job_name: str, **kwargs: Any) -> None:
        await self._pool.enqueue_job(job_name, **kwargs)

    async def close(self) -> None:
        await self._pool.aclose()


class MemoryTaskQueue:
    """In-memory queue for tests — records every enqueued job."""

    def __init__(self) -> None:
        self.jobs: list[dict[str, Any]] = []

    async def enqueue(self, job_name: str, **kwargs: Any) -> None:
        self.jobs.append({"name": job_name, "kwargs": kwargs})

    def clear(self) -> None:
        self.jobs.clear()
