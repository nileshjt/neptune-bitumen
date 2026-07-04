from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean
from sqlalchemy.dialects.postgresql import ARRAY
from database import Base


class Tender(Base):
    __tablename__ = "tenders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tender_id = Column(String(255), unique=True, nullable=False)
    title = Column(Text, nullable=False)
    country = Column(String(100))
    region = Column(String(50))
    buyer = Column(String(500))
    quantity_mt = Column(Float)
    grade_spec = Column(String(200))
    submission_deadline = Column(DateTime)
    estimated_value_usd = Column(Float)
    currency = Column(String(10))
    source_url = Column(Text)
    document_urls = Column(ARRAY(Text), default=[])
    raw_text = Column(Text)
    scraped_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    status = Column(String(20), default="active")
    awarded_price_usd = Column(Float)
    notified = Column(Boolean, default=False)


class AlertSubscription(Base):
    __tablename__ = "alert_subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255))
    whatsapp = Column(String(50))
    keywords = Column(ARRAY(Text), default=[])
    regions = Column(ARRAY(Text), default=[])
    min_quantity_mt = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    active = Column(Boolean, default=True)
