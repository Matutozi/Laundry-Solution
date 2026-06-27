import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.queue import ArqTaskQueue, MemoryTaskQueue

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        from arq import create_pool
        from arq.connections import RedisSettings

        from app.config import settings

        pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        app.state.task_queue = ArqTaskQueue(pool)
        logger.info("arq connected to Redis")
    except Exception as exc:
        logger.warning("Redis unavailable (%s) — using in-memory task queue", exc)
        app.state.task_queue = MemoryTaskQueue()

    yield

    if isinstance(getattr(app.state, "task_queue", None), ArqTaskQueue):
        await app.state.task_queue.close()


from app.routers.admin import router as admin_router
from app.routers.auth import router as auth_router
from app.routers.customers import router as customers_router
from app.routers.health import router as health_router
from app.routers.order_actions import router as order_actions_router
from app.routers.orders import router as orders_router
from app.routers.pickup import router as pickup_router
from app.routers.sync import router as sync_router

app = FastAPI(title="Wise-Wash API", lifespan=lifespan)

app.include_router(health_router)
app.include_router(admin_router)
app.include_router(auth_router)
app.include_router(customers_router)
app.include_router(orders_router)
app.include_router(order_actions_router)
app.include_router(pickup_router)
app.include_router(sync_router)
