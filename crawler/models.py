from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Text, Boolean,
    UniqueConstraint, ForeignKey, func
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Tender(Base):
    __tablename__ = "tenders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tender_id = Column(String(255), unique=True, nullable=False)
    title = Column(Text, nullable=False)
    country = Column(String(100))
    region = Column(String(50))  # africa / southeast_asia / india
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
    status = Column(String(20), default="active")  # active / awarded / closed / cancelled
    awarded_price_usd = Column(Float)
    notified = Column(Boolean, default=False)

    def to_dict(self):
        return {
            "id": self.id,
            "tender_id": self.tender_id,
            "title": self.title,
            "country": self.country,
            "region": self.region,
            "buyer": self.buyer,
            "quantity_mt": self.quantity_mt,
            "grade_spec": self.grade_spec,
            "submission_deadline": self.submission_deadline.isoformat() if self.submission_deadline else None,
            "estimated_value_usd": self.estimated_value_usd,
            "currency": self.currency,
            "source_url": self.source_url,
            "document_urls": self.document_urls or [],
            "scraped_at": self.scraped_at.isoformat() if self.scraped_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "status": self.status,
            "awarded_price_usd": self.awarded_price_usd,
        }


class CrawlLog(Base):
    __tablename__ = "crawl_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_name = Column(String(100), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime)
    tenders_found = Column(Integer, default=0)
    errors = Column(Text)


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
