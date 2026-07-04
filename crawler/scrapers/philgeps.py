"""
PhilGEPS — Philippine Government Electronic Procurement System
notices.philgeps.gov.ph — legally mandated for all Philippine govt procurement.
Has a semi-public JSON API used by its own frontend.
"""
import logging
import hashlib
from datetime import datetime
from typing import Optional
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base_scraper import BaseScraper

logger = logging.getLogger(__name__)

PHILGEPS_SEARCH_URL  = "https://notices.philgeps.gov.ph/GEPSNONPILOT/Tender/SplashOpportunitiesSearchUI.aspx"
PHILGEPS_API_BASE    = "https://notices.philgeps.gov.ph"


class PhilGEPSScraper(BaseScraper):
    def __init__(self):
        super().__init__("philgeps")

    def get_tenders(self) -> list[dict]:
        tenders = []
        keywords = ["bitumen", "asphalt", "road surfacing", "bituminous", "pavement", "overlay", "hot mix"]

        for keyword in keywords:
            logger.info(f"Searching PhilGEPS for: {keyword}")
            results = self._search_philgeps(keyword)
            for item in results:
                text = f"{item.get('title','')} {item.get('description','')} {item.get('category','')}"
                if self.is_bitumen_related(text):
                    tender = self._parse_item(item)
                    if tender:
                        tenders.append(tender)
                        self.save_tender(tender)

        logger.info(f"PhilGEPS: found {len(tenders)} bitumen tenders")
        return tenders

    def _search_philgeps(self, keyword: str) -> list[dict]:
        from bs4 import BeautifulSoup
        items = []

        # PhilGEPS uses ASP.NET WebForms — try the search endpoint
        params = {
            "ctl00$cphMain$txtKeyword": keyword,
            "ctl00$cphMain$ddlCategory": "0",
            "ctl00$cphMain$ddlStatus": "1",  # Active/Open
            "ctl00$cphMain$btnSearch": "Search",
        }

        # First GET to retrieve viewstate
        response = self.get_with_retry(PHILGEPS_SEARCH_URL)
        if not response:
            return []

        try:
            soup = BeautifulSoup(response.text, "lxml")
            viewstate = soup.find("input", {"id": "__VIEWSTATE"})
            eventval = soup.find("input", {"id": "__EVENTVALIDATION"})

            post_data = {
                "__VIEWSTATE": viewstate["value"] if viewstate else "",
                "__EVENTVALIDATION": eventval["value"] if eventval else "",
                "ctl00$cphMain$txtKeyword": keyword,
                "ctl00$cphMain$ddlStatus": "1",
                "ctl00$cphMain$btnSearch": "Search",
            }

            post_response = self.client.post(PHILGEPS_SEARCH_URL, data=post_data, timeout=30)
            if not post_response or post_response.status_code != 200:
                return []

            result_soup = BeautifulSoup(post_response.text, "lxml")
            table = result_soup.find("table", {"id": lambda x: x and "grid" in x.lower()})
            if not table:
                table = result_soup.find("table", class_=lambda c: c and ("grid" in c.lower() or "list" in c.lower()))

            if not table:
                return []

            for row in table.find_all("tr")[1:]:
                cells = row.find_all("td")
                if len(cells) < 4:
                    continue
                link = row.find("a")
                title = link.get_text(strip=True) if link else cells[1].get_text(strip=True)
                href = link["href"] if link and link.get("href") else ""
                if href and not href.startswith("http"):
                    href = f"{PHILGEPS_API_BASE}{href}"

                ref = cells[0].get_text(strip=True)
                entity = cells[2].get_text(strip=True) if len(cells) > 2 else ""
                deadline = cells[-1].get_text(strip=True) if cells else ""

                items.append({
                    "title": title,
                    "ref": ref,
                    "entity": entity,
                    "deadline_text": deadline,
                    "url": href,
                })

        except Exception as e:
            logger.error(f"PhilGEPS scrape error for '{keyword}': {e}")

        return items

    def _parse_item(self, item: dict) -> Optional[dict]:
        title = item.get("title", "")
        if not title:
            return None

        ref = item.get("ref", "")
        tender_id = f"PHILGEPS-{ref}" if ref else f"PHILGEPS-{hashlib.md5(title.encode()).hexdigest()[:12]}"

        deadline = None
        raw = item.get("deadline_text", "")
        if raw:
            for fmt in ["%m/%d/%Y %I:%M %p", "%m/%d/%Y", "%Y-%m-%d", "%d %b %Y"]:
                try:
                    deadline = datetime.strptime(raw.strip()[:20], fmt)
                    break
                except ValueError:
                    continue

        source_url = item.get("url", "https://notices.philgeps.gov.ph")
        ai_info = self.extract_tender_info(f"{title} {item.get('entity','')}", source_url)

        return {
            "tender_id": tender_id,
            "title": title[:500],
            "country": "Philippines",
            "region": "southeast_asia",
            "buyer": item.get("entity", "Philippine Government"),
            "quantity_mt": ai_info.get("quantity_mt"),
            "grade_spec": ai_info.get("grade_spec"),
            "submission_deadline": deadline or ai_info.get("submission_deadline"),
            "estimated_value_usd": ai_info.get("estimated_value_usd"),
            "currency": "PHP",
            "source_url": source_url,
            "document_urls": [],
            "raw_text": str(item)[:2000],
            "status": "active",
        }
