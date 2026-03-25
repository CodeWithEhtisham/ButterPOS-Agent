from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from .base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=True)
    role = Column(String(50), nullable=False, default="cashier")  # owner, manager, cashier, server
    provider_contact_id = Column(String(255), nullable=True, index=True)
    language_pref = Column(String(10), nullable=False, default="en")  # en, ur, mixed

    restaurant = relationship("Restaurant", back_populates="users")
    branch = relationship("Branch", back_populates="users")
