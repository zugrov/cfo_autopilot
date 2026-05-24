from arq import cron
from arq.connections import RedisSettings

from app.core.config import get_settings
from app.workers.tasks import task_recompute_snapshot, task_send_telegram_digest, startup, shutdown

settings = get_settings()


class WorkerSettings:
    functions = [task_recompute_snapshot, task_send_telegram_digest]
    # Дайджест в 08:00 MSK = 05:00 UTC
    cron_jobs = [
        cron(task_send_telegram_digest, hour=5, minute=0, unique=True),
    ]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 10
    job_timeout = 300  # 5 минут
