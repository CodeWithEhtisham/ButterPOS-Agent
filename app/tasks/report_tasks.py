"""Fortnightly report generation."""

from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.report_tasks.generate_fortnightly_report")
def generate_fortnightly_report():
    """Generate and email fortnightly support performance reports."""
    pass
