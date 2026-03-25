"""Ticket sync polling fallback — every 10 min."""

from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.polling_fallback.sync_tickets")
def sync_tickets():
    """Poll ticketing platform for missed webhook events."""
    pass
