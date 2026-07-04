"""
Central Public Procurement Portal — eprocure.gov.in
Covers NHAI, NHIDCL, MoRTH, and all central govt ministries.
Scrapes the public tender search page (no auth required).
"""
import logging
import hashlib
from datetime import datetime
from typing import Optional
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base_scraper import BaseScraper

logger = logging.getLogger(__name__)

CPPP_SEARCH_URL = "https://eprocure.gov.in/cppp/tendersearchlist"
CPPP_API_URL    = "https://eprocure.gov.in/eprocure/app?service=page/TendersByOrganisation"

ROAD_ORGS = [
    "National Highways Authority",
    "NHAI",
    "NHIDCL",
    "Ministry of Road Transport",
    "MoRTH",
    "Border Roads Organisation",
    "BRO",
    "CPWD",
    "National Highways & Infrastructure",
]


class CPPPIndiaScraper(BaseScraper):
    def __init__(self):
        super().__init__("cppp_india")
        self.base_url = "https://eprocure.gov.in"

    def get_tenders(self) -> list[dict]:
        tenders = []
        keywords = ["bitumen supply", "supply of bitumen", "VG-30", "VG-10", "PMB", "CRMB", "bitumen emulsion", "bituminous material"]

        for keyword in keywords:
            logger.info(f"Searching CPPP for: {keyword}")
            results = self._search_cppp(keyword)
            for item in results:
                text = f"{item.get('title','')} {item.get('org','')} {item.get('dept','')}"
                if self.is_bitumen_related(text):
                    tender = self._parse_item(item)
                    if tender:
                        tenders.append(tender)
                        self.save_tender(tender)

        logger.info(f"CPPP India: found {len(tenders)} bitumen tenders")
        return tenders

    def _search_cppp(self, keyword: str) -> list[dict]:
        from bs4 import BeautifulSoup
        items = []
        page = 1

        while page <= 5:
            params = {
                "searchText": keyword,
                "pageNumber": page,
                "tenderStatus": "active",
            }
            headers = {
                "Accept": "text/html,application/xhtml+xml",
                "Referer": "https://eprocure.gov.in/cppp/tendersearchlist",
            }
            response = self.get_with_retry(CPPP_SEARCH_URL, params=params)
            if not response:
                break

            try:
                soup = BeautifulSoup(response.text, "lxml")

                # CPPP renders a table with tender rows
                table = soup.find("table", {"id": "table"}) or soup.find("table", class_=lambda c: c and "list" in c.lower())
                if not table:
                    # Try generic table
                    tables = soup.find_all("table")
                    table = tables[1] if len(tables) > 1 else (tables[0] if tables else None)

                if not table:
                    break

                rows = table.find_all("tr")[1:]  # skip header
                if not rows:
                    break

                for row in rows:
                    cells = row.find_all("td")
                    if len(cells) < 4:
                        continue

                    link = row.find("a")
                    title = link.get_text(strip=True) if link else cells[1].get_text(strip=True)
                    href = link["href"] if link and link.get("href") else ""
                    if href and not href.startswith("http"):
                        href = f"{self.base_url}{href}"

                    org = cells[2].get_text(strip=True) if len(cells) > 2 else ""
                    deadline_text = cells[-2].get_text(strip=True) if len(cells) > 4 else cells[-1].get_text(strip=True)
                    ref_no = cells[0].get_text(strip=True)

                    items.append({
                        "title": title,
                        "ref_no": ref_no,
                        "org": org,
                        "deadline_text": deadline_text,
                        "url": href,
                    })

                # Check for next page
                next_btn = soup.find("a", string=lambda s: s and ("next" in s.lower() or "»" in s))
                if not next_btn:
                    break
                page += 1

            except Exception as e:
                logger.error(f"CPPP parse error page {page}: {e}")
                break

        return items

    def _parse_item(self, item: dict) -> Optional[dict]:
        title = item.get("title", "")
        if not title:
            return None

        ref = item.get("ref_no", "")
        tender_id = f"CPPP-{ref}" if ref else f"CPPP-{hashlib.md5(title.encode()).hexdigest()[:12]}"

        deadline = None
        raw = item.get("deadline_text", "")
        if raw:
            for fmt in ["%d-%b-%Y", "%d/%m/%Y %H:%M", "%d/%m/%Y", "%Y-%m-%d"]:
                try:
                    deadline = datetime.strptime(raw.strip()[:20], fmt)
                    break
                except ValueError:
                    continue

        source_url = item.get("url", "https://eprocure.gov.in/cppp/tendersearchlist")
        ai_info = self.extract_tender_info(f"{title} {item.get('org','')}", source_url)

        return {
            "tender_id": tender_id,
            "title": title[:500],
            "country": "India",
            "region": "india",
            "buyer": item.get("org", "Government of India"),
            "quantity_mt": ai_info.get("quantity_mt"),
            "grade_spec": ai_info.get("grade_spec"),
            "submission_deadline": deadline or ai_info.get("submission_deadline"),
            "estimated_value_usd": ai_info.get("estimated_value_usd"),
            "currency": "INR",
            "source_url": source_url,
            "document_urls": [],
            "raw_text": str(item)[:2000],
            "status": "active",
        }
