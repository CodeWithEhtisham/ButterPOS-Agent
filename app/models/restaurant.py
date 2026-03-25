from sqlalchemy import Column, Integer, String, Boolean, Date
from sqlalchemy.orm import relationship

from .base import Base, TimestampMixin


class Restaurant(Base, TimestampMixin):
    __tablename__ = "restaurants"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    plan_type = Column(String(20), nullable=False, default="8h")  # 8h, 16h, 24_7
    plan_status = Column(String(20), nullable=False, default="active")  # active, expired, suspended
    payment_due = Column(Boolean, default=False, nullable=False)
    plan_expiry = Column(Date, nullable=True)

    branches = relationship("Branch", back_populates="restaurant", lazy="selectin")
    users = relationship("User", back_populates="restaurant", lazy="selectin")
