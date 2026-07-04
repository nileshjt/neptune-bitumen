from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from database import get_db
from models import AlertSubscription

router = APIRouter(prefix="/alerts", tags=["alerts"])


class SubscriptionCreate(BaseModel):
    email: Optional[str] = None
    whatsapp: Optional[str] = None
    keywords: list[str] = []
    regions: list[str] = []
    min_quantity_mt: float = 0.0


class SubscriptionOut(BaseModel):
    id: int
    email: Optional[str]
    whatsapp: Optional[str]
    keywords: Optional[list[str]]
    regions: Optional[list[str]]
    min_quantity_mt: Optional[float]
    active: bool

    model_config = {"from_attributes": True}


@router.post("/subscribe", response_model=SubscriptionOut, status_code=201)
def subscribe(payload: SubscriptionCreate, db: Session = Depends(get_db)):
    if not payload.email and not payload.whatsapp:
        raise HTTPException(status_code=400, detail="Provide email or whatsapp number")

    sub = AlertSubscription(
        email=payload.email,
        whatsapp=payload.whatsapp,
        keywords=payload.keywords,
        regions=payload.regions,
        min_quantity_mt=payload.min_quantity_mt,
        active=True,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


@router.get("/subscriptions", response_model=list[SubscriptionOut])
def list_subscriptions(db: Session = Depends(get_db)):
    return db.query(AlertSubscription).filter_by(active=True).all()


@router.delete("/subscriptions/{subscription_id}", status_code=204)
def delete_subscription(subscription_id: int, db: Session = Depends(get_db)):
    sub = db.query(AlertSubscription).filter_by(id=subscription_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    sub.active = False
    db.commit()
