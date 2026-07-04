import re
import time
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional
import httpx
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import anthropic

from config import DATABASE_URL, ANTHROPIC_API_KEY, GEMINI_API_KEY
from models import Tender, Base
from sqlalchemy import create_engine

logger = logging.getLogger(__name__)

# Keywords that indicate bitumen/asphalt as a PRODUCT being procured
BITUMEN_SUPPLY_KEYWORDS = [
    "supply of bitumen", "supply of asphalt", "procurement of bitumen",
    "purchase of bitumen", "bitumen supply", "bitumen procurement",
    "asphalt supply", "asphalt procurement", "bitumen delivery",
    "bitumen emulsion", "bitumen grade", "bitumen vg", "vg-10", "vg-30", "vg-40",
    "vg10", "vg30", "vg40", "pmb", "crmb", "pen grade", "penetration grade",
    "60/70", "80/100", "40/60", "bitumen 60", "bitumen 80",
    "bulk bitumen", "drum bitumen", "tank bitumen", "tanker bitumen",
    "bituminous material", "bituminous product",
    "tack coat", "prime coat", "bituminous binder",
    # French
    "fourniture de bitume", "fourniture bitume",
    # Bahasa
    "pengadaan aspal", "aspal bulk",
]

# Keywords that indicate road CONSTRUCTION/WORKS (exclude these)
ROAD_WORKS_EXCLUDE = [
    "road to bitumen standard", "upgrading to bitumen", "upgrading of road",
    "road construction", "road surfacing", "road maintenance", "road rehabilitation",
    "road improvement", "pavement construction", "road works", "roadworks",
    "bituminous road", "bitumen road", "asphalt road", "asphalt laying",
    "asphalt paving", "road paving", "road sealing", "chip seal", "surface dressing",
    "double surface dressing", "single surface dressing", "road reseal",
    "bituminous surfacing", "bituminous pavement", "bituminous wearing",
    "wearing course", "binder course", "dense bituminous macadam",
    "hot mix asphalt", "HMA", "hot bituminous mix", "DBM", "WMM",
    "municipal roads", "district roads", "provincial roads", "trunk roads",
    "renovation of bitumen surface", "renovation of asphalt",
    "maintenance of bitumen", "maintenance of asphalt",
    "bituminous concrete works", "road to blacktop",
]

engine = create_engine(DATABASE_URL)


class BaseScraper(ABC):
    def __init__(self, source_name: str):
        self.source_name = source_name
        self.client = httpx.Client(
            timeout=30.0,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; NeptuneBitumenBot/1.0; +https://neptunepetro.com/bot)"
            },
            follow_redirects=True,
        )
        self.anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None
        self.gemini_api_key = GEMINI_API_KEY or None

    @abstractmethod
    def get_tenders(self) -> list[dict]:
        """Scrape tenders from the source. Returns list of tender dicts."""
        pass

    def is_bitumen_related(self, text: str) -> bool:
        """Check if text is about bitumen/asphalt SUPPLY/PROCUREMENT (not road construction)."""
        if not text:
            return False
        text_lower = text.lower()

        # Reject road construction/works tenders
        for excl in ROAD_WORKS_EXCLUDE:
            if excl.lower() in text_lower:
                return False

        # Accept only supply/procurement keywords
        for kw in BITUMEN_SUPPLY_KEYWORDS:
            if kw.lower() in text_lower:
                return True

        return False

    def extract_tender_info(self, text: str, url: str) -> dict:
        """Use Gemini Flash to extract structured procurement info from tender text."""
        if not self.gemini_api_key:
            return {}

        prompt = f"""Extract procurement information from this tender text. Return ONLY a valid JSON object with these fields:
- quantity_mt: numeric quantity in metric tons (null if not found, convert from other units)
- grade_spec: bitumen grade specification (e.g. "VG-30", "60/70 pen", "PMB 40") or null
- estimated_value_usd: contract value in USD (null if not found, convert from local currency)
- currency: original currency code (null if not found)
- submission_deadline: deadline as YYYY-MM-DDTHH:MM:SS (null if not found)
- buyer: procuring entity / buyer organization name
- title: concise title of what is being procured (max 100 chars)

Tender URL: {url}
Tender Text:
{text[:3000]}

Return ONLY valid JSON, no markdown, no explanation."""

        gemini_url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-2.0-flash:generateContent?key={self.gemini_api_key}"
        )

        for attempt in range(3):
            try:
                resp = self.client.post(
                    gemini_url,
                    json={"contents": [{"parts": [{"text": prompt}]}]},
                    timeout=20.0,
                )
                resp.raise_for_status()
                raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                raw = re.sub(r"^```(?:json)?\n?", "", raw)
                raw = re.sub(r"\n?```$", "", raw)
                return json.loads(raw)
            except json.JSONDecodeError as e:
                logger.warning(f"Gemini JSON parse error attempt {attempt+1}: {e}")
                if attempt < 2:
                    time.sleep(2 ** attempt)
            except Exception as e:
                logger.error(f"Gemini extraction error: {e}")
                if attempt < 2:
                    time.sleep(2 ** attempt)
        return {}

    def save_tender(self, tender_dict: dict) -> Optional[Tender]:
        """Save or update a tender in the database."""
        with Session(engine) as session:
            try:
                existing = session.query(Tender).filter_by(
                    tender_id=tender_dict.get("tender_id")
                ).first()

                if existing:
                    for key, value in tender_dict.items():
                        if key != "id" and hasattr(existing, key):
                            setattr(existing, key, value)
                    existing.updated_at = datetime.utcnow()
                    session.commit()
                    logger.info(f"Updated tender: {tender_dict.get('tender_id')}")
                    return existing
                else:
                    tender = Tender(**{
                        k: v for k, v in tender_dict.items()
                        if hasattr(Tender, k) and k != "id"
                    })
                    session.add(tender)
                    session.commit()
                    session.refresh(tender)
                    logger.info(f"Saved new tender: {tender_dict.get('tender_id')}")
                    return tender
            except IntegrityError as e:
                session.rollback()
                logger.warning(f"Integrity error saving tender: {e}")
                return None
            except Exception as e:
                session.rollback()
                logger.error(f"Error saving tender: {e}")
                return None

    def get_with_retry(self, url: str, params: dict = None, max_retries: int = 3) -> Optional[httpx.Response]:
        """GET request with exponential backoff."""
        for attempt in range(max_retries):
            try:
                response = self.client.get(url, params=params)
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    wait = 2 ** (attempt + 1)
                    logger.warning(f"Rate limited by {url}, waiting {wait}s")
                    time.sleep(wait)
                elif e.response.status_code >= 500:
                    wait = 2 ** attempt
                    logger.warning(f"Server error {e.response.status_code}, retrying in {wait}s")
                    time.sleep(wait)
                else:
                    logger.error(f"HTTP error {e.response.status_code} for {url}")
                    return None
            except httpx.RequestError as e:
                wait = 2 ** attempt
                logger.warning(f"Request error for {url}: {e}, retrying in {wait}s")
                time.sleep(wait)
        return None

    def close(self):
        self.client.close()
