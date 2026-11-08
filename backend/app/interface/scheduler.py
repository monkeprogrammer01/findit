from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.application.retention import run_retention_job


def create_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="UTC")
    # каждый день в 03:00 UTC; повторный запуск безопасен, ничего не пометит дважды
    scheduler.add_job(
        run_retention_job, CronTrigger(hour=3, minute=0), id="retention", replace_existing=True
    )
    return scheduler
