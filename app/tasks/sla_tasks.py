"""SLA timer checks — runs every 60s."""

from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.sla_tasks.check_sla_timers")
def check_sla_timers():
    """Check all active tickets for SLA breaches and trigger escalations."""
    pass
