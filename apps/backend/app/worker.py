"""arq worker — run with: arq app.worker.WorkerSettings"""

from arq.connections import RedisSettings

from app.config import settings
from app.database import engine
from app.jobs.receipts import send_receipt
from app.notifications.real import RealNotificationProvider


async def startup(ctx: dict) -> None:
    ctx["db_engine"] = engine
    ctx["notification_provider"] = RealNotificationProvider()


async def shutdown(ctx: dict) -> None:
    pass


class WorkerSettings:
    functions = [send_receipt]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    on_startup = startup
    on_shutdown = shutdown
