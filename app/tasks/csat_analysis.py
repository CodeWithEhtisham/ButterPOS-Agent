"""Weekly CSAT analysis."""

from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.csat_analysis.analyze_weekly_csat")
def analyze_weekly_csat():
    """Analyze weekly CSAT scores and generate insights."""
    pass
