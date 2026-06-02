"""ORM table models — import here so Base.metadata is complete for Alembic."""

from app.db.models.ai_conversation import AIConversation
from app.db.models.branch import Branch
from app.db.models.kb_article import KBArticle
from app.db.models.kb_article_version import KBArticleVersion
from app.db.models.restaurant import Restaurant
from app.db.models.sla_config import SLAConfig
from app.db.models.ticket_cache import TicketCache
from app.db.models.user import User
from app.db.models.webhook_event_log import WebhookEventLog

__all__ = [
    "AIConversation",
    "Branch",
    "KBArticle",
    "KBArticleVersion",
    "Restaurant",
    "SLAConfig",
    "TicketCache",
    "User",
    "WebhookEventLog",
]
