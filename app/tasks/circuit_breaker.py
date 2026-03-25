"""AI health monitoring — every 5 min."""

from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.circuit_breaker.check_ai_health")
def check_ai_health():
    """Monitor AI response quality and toggle circuit breaker if needed."""
    pass
