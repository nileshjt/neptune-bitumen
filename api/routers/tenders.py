import io
from datetime import datetime
from typing import Optional
import pandas as pd
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from database import get_db
from models import Tender

router = APIRouter(prefix="/tenders", tags=["tenders"])


class TenderOut(BaseModel):
    id: int
    tender_id: str
    title: str
    country: Optional[str]
    region: Optional[str]
    buyer: Optional[str]
    quantity_mt: Optional[float]
    grade_spec: Optional[str]
    submission_deadline: Optional[datetime]
    estimated_value_usd: Optional[float]
    currency: Optional[str]
    source_url: Optional[str]
    document_urls: Optional[list[str]]
    raw_text: Optional[str]
    scraped_at: Optional[datetime]
    status: Optional[str]
    awarded_price_usd: Optional[float]

    model_config = {"from_attributes": True}


class TenderListResponse(BaseModel):
    total: int
    page: int
    per_page: int
    items: list[TenderOut]


class StatsResponse(BaseModel):
    total_active: int
    by_region: dict
    by_status: dict
    total_estimated_value_usd: Optional[float]
    avg_quantity_mt: Optional[float]
    countries_covered: int
    new_this_week: int


def _build_query(
    db: Session,
    region: Optional[str],
    country: Optional[str],
    status: Optional[str],
    min_quantity_mt: Optional[float],
    max_quantity_mt: Optional[float],
    grade_spec: Optional[str],
    deadline_before: Optional[datetime],
    deadline_after: Optional[datetime],
    search: Optional[str],
):
    q = db.query(Tender)
    if region:
        q = q.filter(Tender.region == region)
    if country:
        q = q.filter(Tender.country.ilike(f"%{country}%"))
    if status:
        q = q.filter(Tender.status == status)
    if min_quantity_mt is not None:
        q = q.filter(Tender.quantity_mt >= min_quantity_mt)
    if max_quantity_mt is not None:
        q = q.filter(Tender.quantity_mt <= max_quantity_mt)
    if grade_spec:
        q = q.filter(Tender.grade_spec.ilike(f"%{grade_spec}%"))
    if deadline_before:
        q = q.filter(Tender.submission_deadline <= deadline_before)
    if deadline_after:
        q = q.filter(Tender.submission_deadline >= deadline_after)
    if search:
        q = q.filter(
            Tender.title.ilike(f"%{search}%") | Tender.buyer.ilike(f"%{search}%")
        )
    return q


@router.get("", response_model=TenderListResponse)
def list_tenders(
    region: Optional[str] = Query(None, description="africa | southeast_asia | india"),
    country: Optional[str] = Query(None),
    status: Optional[str] = Query(None, description="active | awarded | closed | cancelled"),
    min_quantity_mt: Optional[float] = Query(None),
    max_quantity_mt: Optional[float] = Query(None),
    grade_spec: Optional[str] = Query(None),
    deadline_before: Optional[datetime] = Query(None),
    deadline_after: Optional[datetime] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    q = _build_query(
        db, region, country, status, min_quantity_mt, max_quantity_mt,
        grade_spec, deadline_before, deadline_after, search,
    )
    total = q.count()
    items = (
        q.order_by(Tender.scraped_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return TenderListResponse(total=total, page=page, per_page=per_page, items=items)


@router.get("/stats", response_model=StatsResponse)
def get_stats(db: Session = Depends(get_db)):
    from datetime import timedelta

    total_active = db.query(Tender).filter(Tender.status == "active").count()

    by_region_rows = (
        db.query(Tender.region, func.count(Tender.id))
        .group_by(Tender.region)
        .all()
    )
    by_region = {r: c for r, c in by_region_rows if r}

    by_status_rows = (
        db.query(Tender.status, func.count(Tender.id))
        .group_by(Tender.status)
        .all()
    )
    by_status = {s: c for s, c in by_status_rows if s}

    total_value = db.query(func.sum(Tender.estimated_value_usd)).scalar()
    avg_qty = db.query(func.avg(Tender.quantity_mt)).scalar()
    countries = db.query(func.count(func.distinct(Tender.country))).scalar()

    week_ago = datetime.utcnow() - timedelta(days=7)
    new_this_week = db.query(Tender).filter(Tender.scraped_at >= week_ago).count()

    return StatsResponse(
        total_active=total_active,
        by_region=by_region,
        by_status=by_status,
        total_estimated_value_usd=float(total_value) if total_value else None,
        avg_quantity_mt=float(avg_qty) if avg_qty else None,
        countries_covered=countries or 0,
        new_this_week=new_this_week,
    )


@router.get("/export/csv")
def export_csv(
    region: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    min_quantity_mt: Optional[float] = Query(None),
    max_quantity_mt: Optional[float] = Query(None),
    grade_spec: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    q = _build_query(db, region, country, status, min_quantity_mt, max_quantity_mt, grade_spec, None, None, search)
    tenders = q.order_by(Tender.scraped_at.desc()).limit(5000).all()

    rows = [
        {
            "Tender ID": t.tender_id,
            "Title": t.title,
            "Country": t.country,
            "Region": t.region,
            "Buyer": t.buyer,
            "Quantity (MT)": t.quantity_mt,
            "Grade Spec": t.grade_spec,
            "Deadline": t.submission_deadline.isoformat() if t.submission_deadline else "",
            "Est. Value (USD)": t.estimated_value_usd,
            "Currency": t.currency,
            "Status": t.status,
            "Source URL": t.source_url,
            "Scraped At": t.scraped_at.isoformat() if t.scraped_at else "",
        }
        for t in tenders
    ]
    df = pd.DataFrame(rows)
    output = io.StringIO()
    df.to_csv(output, index=False)
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=neptune_bitumen_tenders.csv"},
    )


@router.get("/export/excel")
def export_excel(
    region: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    min_quantity_mt: Optional[float] = Query(None),
    max_quantity_mt: Optional[float] = Query(None),
    grade_spec: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    q = _build_query(db, region, country, status, min_quantity_mt, max_quantity_mt, grade_spec, None, None, search)
    tenders = q.order_by(Tender.scraped_at.desc()).limit(5000).all()

    rows = [
        {
            "Tender ID": t.tender_id,
            "Title": t.title,
            "Country": t.country,
            "Region": t.region,
            "Buyer": t.buyer,
            "Quantity (MT)": t.quantity_mt,
            "Grade Spec": t.grade_spec,
            "Deadline": t.submission_deadline,
            "Est. Value (USD)": t.estimated_value_usd,
            "Currency": t.currency,
            "Status": t.status,
            "Source URL": t.source_url,
            "Scraped At": t.scraped_at,
        }
        for t in tenders
    ]
    df = pd.DataFrame(rows)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Bitumen Tenders")
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=neptune_bitumen_tenders.xlsx"},
    )


@router.get("/{tender_id_or_id}", response_model=TenderOut)
def get_tender(tender_id_or_id: str, db: Session = Depends(get_db)):
    tender = None
    if tender_id_or_id.isdigit():
        tender = db.query(Tender).filter(Tender.id == int(tender_id_or_id)).first()
    if not tender:
        tender = db.query(Tender).filter(Tender.tender_id == tender_id_or_id).first()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")
    return tender
