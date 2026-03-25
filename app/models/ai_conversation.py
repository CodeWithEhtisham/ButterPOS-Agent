from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from .base import Base, TimestampMixin


class AIConversation(Base, TimestampMixin):
    __tablename__ = "ai_conversations"

    id = Column(Integer, primary_key=True, index=True)
    ticket_cache_id = Column(Integer, ForeignKey("ticket_cache.id"), nullable=False, index=True)
    messages_json = Column(JSONB, default=list, nullable=False)
    confidence_history = Column(JSONB, default=list, nullable=False)
    kb_articles_used = Column(JSONB, default=list, nullable=False)
    conversation_summary = Column(Text, nullable=True)
    feedback_flag = Column(Boolean, default=False, nullable=False)

    ticket_cache = relationship("TicketCache", back_populates="conversations")
