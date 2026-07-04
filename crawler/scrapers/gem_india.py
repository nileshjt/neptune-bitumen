import logging
import hashlib
from datetime import datetime
from typing import Optional
import httpx
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base_scraper import BaseScraper

logger = logging.getLogger(__name__)

GEM_SEARCH_URL = "https://bidplus.gem.gov.in/all-bids"
GEM_API_URL = "https://bidplus.gem.gov.in/bidlists"


class GeMIndiaScraper(BaseScraper):
    def __init__(self):
        super().__init__("gem_india")
        self.base_url = "https://bidplus.gem.gov.in"

    def get_tenders(self) -> list[dict]:
        tenders = []
        keywords = ["bitumen", "VG-30", "VG-10", "PMB", "CRMB", "bitumen emulsion", "drum bitumen", "bulk bitumen"]

        for keyword in keywords:
            logger.info(f"Searching GeM for: {keyword}")
            page = 1
            while page <= 5:  # Limit to 5 pages per keyword
                results = self._search_gem(keyword, page)
                if not results:
                    break
                for item in results:
                    if self.is_bitumen_related(
                        f"{item.get('bid_title', '')} {item.get('category', '')} {item.get('department', '')}"
                    ):
                        tender = self._parse_gem_item(item)
                        if tender:
                            tenders.append(tender)
                            self.save_tender(tender)
                page += 1

        logger.info(f"GeM India: found {len(tenders)} bitumen tenders")
        return tenders

    def _search_gem(self, keyword: str, page: int = 1) -> list[dict]:
        """Search GeM bids API."""
        params = {
            "searchedText": keyword,
            "page": page,
            "bidStatus": "Active",
        }
        headers = {
            "Accept": "application/json",
            "Referer": "https://bidplus.gem.gov.in/all-bids",
            "X-Requested-With": "XMLHttpRequest",
        }
        try:
            response = self.client.get(
                GEM_API_URL,
                params=params,
                headers=headers,
                timeout=30,
            )
            if response.status_code == 200:
                data = response.json()
                # GeM returns data in different structures; try common patterns
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict):
                    return data.get("data", data.get("bids", data.get("result", [])))
        except Exception as e:
            logger.warning(f"GeM API error for '{keyword}' page {page}: {e}")
            # Fallback: try scraping the HTML page
            return self._scrape_gem_html(keyword, page)
        return []

    def _scrape_gem_html(self, keyword: str, page: int) -> list[dict]:
        """Fallback HTML scraping for GeM."""
        from bs4 import BeautifulSoup
        try:
            response = self.get_with_retry(
                GEM_SEARCH_URL,
                params={"searchedText": keyword, "page": page}
            )
            if not response:
                return []
            soup = BeautifulSoup(response.text, "lxml")
            items = []
            # GeM bid cards
            for card in soup.select(".bid-list-card, .card-body, [class*='bid']"):
                title_el = card.select_one("h4, h5, .bid-title, strong")
                bid_no_el = card.select_one(".bid-no, [class*='bid-no'], small")
                dept_el = card.select_one(".department, [class*='dept']")
                date_el = card.select_one(".end-date, [class*='date']")

                title = title_el.get_text(strip=True) if title_el else ""
                if not title:
                    continue
                items.append({
                    "bid_title": title,
                    "bid_number": bid_no_el.get_text(strip=True) if bid_no_el else f"GEM-{hashlib.md5(title.encode()).hexdigest()[:8]}",
                    "department": dept_el.get_text(strip=True) if dept_el else "Government of India",
                    "end_date": date_el.get_text(strip=True) if date_el else None,
                    "source_url": response.url,
                })
            return items
        except Exception as e:
            logger.error(f"GeM HTML scraping error: {e}")
            return []

    def _parse_gem_item(self, item: dict) -> Optional[dict]:
        """Convert GeM API item to Tender dict."""
        title = item.get("bid_title", item.get("title", ""))
        if not title:
            return None

        bid_number = item.get("bid_number", item.get("bidNumber", item.get("id", "")))
        tender_id = f"GEM-{bid_number}" if bid_number else f"GEM-{hashlib.md5(title.encode()).hexdigest()[:12]}"

        deadline = None
        raw_deadline = item.get("end_date", item.get("bidEndDate", item.get("closing_date", "")))
        if raw_deadline:
            for fmt in ["%d-%b-%Y %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y", "%Y-%m-%d"]:
                try:
                    deadline = datetime.strptime(str(raw_deadline).strip(), fmt)
                    break
                except ValueError:
                    continue

        # Extract quantity from title using AI if available
        ai_info = {}
        if ANTHROPIC_API_KEY_AVAILABLE():
            source_url = item.get("source_url", f"https://bidplus.gem.gov.in/bid/{bid_number}")
            ai_info = self.extract_tender_info(
                f"{title} {item.get('category', '')} {item.get('consignee', '')}",
                source_url
            )

        return {
            "tender_id": tender_id,
            "title": title,
            "country": "India",
            "region": "india",
            "buyer": item.get("department", item.get("buyer_name", "Government of India")),
            "quantity_mt": ai_info.get("quantity_mt") or item.get("quantity"),
            "grade_spec": ai_info.get("grade_spec") or item.get("category", ""),
            "submission_deadline": deadline or ai_info.get("submission_deadline"),
            "estimated_value_usd": ai_info.get("estimated_value_usd"),
            "currency": ai_info.get("currency", "INR"),
            "source_url": item.get("source_url", f"https://bidplus.gem.gov.in/bid/{bid_number}"),
            "document_urls": [],
            "raw_text": str(item),
            "status": "active",
        }


def ANTHROPIC_API_KEY_AVAILABLE():
    from config import ANTHROPIC_API_KEY
    return bool(ANTHROPIC_API_KEY)
