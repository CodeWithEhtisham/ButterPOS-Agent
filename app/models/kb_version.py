from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from .base import Base


class KBVersion(Base):
    __tablename__ = "kb_versions"

    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(Integer, ForeignKey("kb_articles.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    content_snapshot = Column(Text, nullable=False)
    content_ur_snapshot = Column(Text, nullable=True)
    changed_by = Column(String(255), nullable=True)
    changed_at = Column(DateTime(timezone=True), nullable=False)
    reason = Column(Text, nullable=True)

    article = relationship("KBArticle", back_populates="versions")
