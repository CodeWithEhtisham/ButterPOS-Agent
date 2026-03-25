from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from .base import Base, TimestampMixin


class Branch(Base, TimestampMixin):
    __tablename__ = "branches"

    id = Column(Integer, primary_key=True, index=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    timezone = Column(String(50), nullable=False, default="Asia/Karachi")
    preferred_devices = Column(JSONB, default=list)

    restaurant = relationship("Restaurant", back_populates="branches")
    users = relationship("User", back_populates="branch", lazy="selectin")
