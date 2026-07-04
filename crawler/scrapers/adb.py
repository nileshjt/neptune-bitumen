import logging
import hashlib
from datetime import datetime
from typing import Optional
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base_scraper import BaseScraper

logger = logging.getLogger(__name__)

ADB_API_URL = "https://www.adb.org/api/procurement/notices"
ADB_SEARCH_URL = "https://www.adb.org/projects/procurement"

SEA_COUNTRIES = {
    "Indonesia", "Philippines", "Vietnam", "Thailand", "Malaysia",
    "Myanmar", "Cambodia", "Lao PDR", "Timor-Leste", "Papua New Guinea",
    "Pacific", "Fiji", "Vanuatu", "Solomon Islands",
}


class ADBScraper(BaseScraper):
    def __init__(self):
        super().__init__("adb")
        self.base_url = "https://www.adb.org"

    def get_tenders(self) -> list[dict]:
        tenders = []
        keywords = ["supply of bitumen", "bitumen supply", "bitumen procurement", "VG-30", "PMB", "CRMB", "bitumen emulsion"]

        for keyword in keywords:
            logger.info(f"Searching ADB for: {keyword}")
            results = self._search_adb(keyword)
            for item in results:
                text = f"{item.get('title', '')} {item.get('description', '')} {item.get('sector', '')}"
                if self.is_bitumen_related(text):
                    tender = self._parse_adb_item(item)
                    if tender:
                        tenders.append(tender)
                        self.save_tender(tender)

        logger.info(f"ADB: found {len(tenders)} bitumen tenders")
        return tenders

    def _search_adb(self, keyword: str) -> list[dict]:
        """Search ADB procurement notices."""
        from bs4 import BeautifulSoup
        all_items = []
        page = 0

        while page < 5:
            params = {
                "keywords": keyword,
                "page": page,
                "sector": "transport",
                "status": "active",
            }
            response = self.get_with_retry(ADB_SEARCH_URL, params=params)
            if not response:
                break

            try:
                if "application/json" in response.headers.get("content-type", ""):
                    data = response.json()
                    items = data.get("notices", data.get("results", []))
                    if not items:
                        break
                    all_items.extend(items)
                    if len(items) < 20:
                        break
                else:
                    soup = BeautifulSoup(response.text, "lxml")
                    items = self._parse_adb_html(soup)
                    if not items:
                        break
                    all_items.extend(items)
                    next_page = soup.select_one("a.next, [rel=next], .pager-next a")
                    if not next_page:
                        break
            except Exception as e:
                logger.error(f"ADB search error for '{keyword}' page {page}: {e}")
                break

            page += 1

        return all_items

    def _parse_adb_html(self, soup) -> list[dict]:
        """Parse ADB procurement listing HTML."""
        items = []
        for row in soup.select("table.views-table tbody tr, .views-row, .procurement-notice"):
            title_el = row.select_one("td.views-field-title a, h3 a, .title a")
            country_el = row.select_one(".country, td.views-field-country")
            date_el = row.select_one(".date, td.views-field-date, time")
            ref_el = row.select_one(".ref, .notice-ref, td.views-field-ref")

            if not title_el:
                continue

            href = title_el.get("href", "")
            if not href.startswith("http"):
                href = f"https://www.adb.org{href}"

            items.append({
                "title": title_el.get_text(strip=True),
                "country": country_el.get_text(strip=True) if country_el else "",
                "deadline_text": date_el.get_text(strip=True) if date_el else "",
                "ref": ref_el.get_text(strip=True) if ref_el else "",
                "url": href,
            })
        return items

    def _parse_adb_item(self, item: dict) -> Optional[dict]:
        title = item.get("title", "")
        if not title:
            return None

        country = item.get("country", item.get("member_country", ""))
        region = "southeast_asia" if any(c in country for c in SEA_COUNTRIES) else None
        if not region:
            return None

        ref = item.get("ref", item.get("id", item.get("notice_id", "")))
        tender_id = f"ADB-{ref}" if ref else f"ADB-{hashlib.md5(title.encode()).hexdigest()[:12]}"

        deadline = None
        for field in ["deadline", "submission_date", "closing_date", "deadline_text"]:
            raw = item.get(field, "")
            if raw:
                for fmt in ["%d %b %Y", "%Y-%m-%d", "%d/%m/%Y", "%B %d, %Y"]:
                    try:
                        deadline = datetime.strptime(str(raw).strip()[:20], fmt)
                        break
                    except ValueError:
                        continue
                if deadline:
                    break

        source_url = item.get("url", item.get("source_url", item.get("link", "")))
        if not source_url:
            source_url = f"https://www.adb.org/projects/procurement"

        ai_info = self.extract_tender_info(
            f"{title} {item.get('description', '')} {item.get('sector', '')}",
            source_url,
        )

        return {
            "tender_id": tender_id,
            "title": title[:500],
            "country": country,
            "region": region,
            "buyer": item.get("executing_agency", item.get("buyer", item.get("agency", "ADB Project"))),
            "quantity_mt": ai_info.get("quantity_mt"),
            "grade_spec": ai_info.get("grade_spec"),
            "submission_deadline": deadline or ai_info.get("submission_deadline"),
            "estimated_value_usd": ai_info.get("estimated_value_usd"),
            "currency": ai_info.get("currency", "USD"),
            "source_url": source_url,
            "document_urls": [],
            "raw_text": str(item)[:2000],
            "status": "active",
        }
