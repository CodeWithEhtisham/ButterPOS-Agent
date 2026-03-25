from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import relationship

from .base import Base, TimestampMixin


class TicketCache(Base, TimestampMixin):
    __tablename__ = "ticket_cache"

    id = Column(Integer, primary_key=True, index=True)
    platform_ticket_id = Column(String(255), unique=True, nullable=False, index=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    status = Column(String(50), nullable=False, default="open")
    ai_confidence = Column(Float, nullable=True)
    resolution_path = Column(String(10), nullable=True)  # A, B, C, human
    csat_score = Column(Integer, nullable=True)
    csat_source = Column(String(20), nullable=True)  # inline, email, push, in_app
    reopen_count = Column(Integer, default=0, nullable=False)

    conversations = relationship("AIConversation", back_populates="ticket_cache", lazy="selectin")
