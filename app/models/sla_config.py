from sqlalchemy import Column, Integer, String

from .base import Base, TimestampMixin


class SLAConfig(Base, TimestampMixin):
    __tablename__ = "sla_configs"

    id = Column(Integer, primary_key=True, index=True)
    plan_type = Column(String(20), unique=True, nullable=False)  # 8h, 16h, 24_7
    response_time_minutes = Column(Integer, nullable=False)
    escalation_l1_minutes = Column(Integer, nullable=False)
    escalation_l2_minutes = Column(Integer, nullable=False)
    escalation_l3_minutes = Column(Integer, nullable=False)
