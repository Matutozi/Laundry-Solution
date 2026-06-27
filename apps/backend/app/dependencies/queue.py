from fastapi import Request

from app.queue import ArqTaskQueue, MemoryTaskQueue


async def get_task_queue(request: Request) -> ArqTaskQueue | MemoryTaskQueue:
    return request.app.state.task_queue
