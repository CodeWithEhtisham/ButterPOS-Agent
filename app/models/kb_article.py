from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.orm import relationship

from .base import Base, TimestampMixin


class KBArticle(Base, TimestampMixin):
    __tablename__ = "kb_articles"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    content_ur = Column(Text, nullable=True)  # Roman Urdu version
    category = Column(String(100), nullable=True, index=True)
    version = Column(Integer, default=1, nullable=False)
    status = Column(String(20), default="draft", nullable=False)  # draft, active, archived
    updated_by = Column(String(255), nullable=True)
    change_reason = Column(Text, nullable=True)

    versions = relationship("KBVersion", back_populates="article", lazy="selectin")
