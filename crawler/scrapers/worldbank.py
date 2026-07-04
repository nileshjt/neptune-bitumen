import logging
import hashlib
from datetime import datetime
from typing import Optional
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base_scraper import BaseScraper

logger = logging.getLogger(__name__)

WB_PROCUREMENT_API = "https://search.worldbank.org/api/v2/procurement"

AFRICA_COUNTRIES = {
    "Ethiopia", "Kenya", "Tanzania", "Uganda", "Rwanda", "Mozambique",
    "Zambia", "Zimbabwe", "Ghana", "Nigeria", "Senegal", "Cameroon",
    "Ivory Coast", "Angola", "Madagascar", "Mali", "Burkina Faso",
    "Niger", "Chad", "Somalia", "South Sudan", "Sudan", "DRC",
    "Congo", "Gabon", "Botswana", "Namibia", "South Africa",
    "Morocco", "Algeria", "Tunisia", "Libya", "Egypt",
}

SEA_COUNTRIES = {
    "Indonesia", "Philippines", "Vietnam", "Thailand", "Malaysia",
    "Myanmar", "Cambodia", "Laos", "Timor-Leste", "Papua New Guinea",
}


class WorldBankScraper(BaseScraper):
    def __init__(self):
        super().__init__("worldbank")

    def get_tenders(self) -> list[dict]:
        tenders = []
        keywords = ["supply of bitumen", "bitumen supply", "bitumen procurement", "VG-30", "PMB", "CRMB", "bitumen emulsion", "bulk bitumen"]

        for keyword in keywords:
            logger.info(f"Searching World Bank STEP for: {keyword}")
            results = self._search_worldbank(keyword)
            for item in results:
                if self.is_bitumen_related(
                    f"{item.get('proj_name', '')} {item.get('contract_desc', '')} {item.get('notice_type', '')}"
                ):
                    tender = self._parse_wb_item(item)
                    if tender:
                        tenders.append(tender)
                        self.save_tender(tender)

        logger.info(f"World Bank: found {len(tenders)} bitumen tenders")
        return tenders

    def _search_worldbank(self, keyword: str) -> list[dict]:
        """Search World Bank STEP procurement API."""
        all_results = []
        page = 1
        per_page = 50

        while page <= 10:
            params = {
                "format": "json",
                "qterm": keyword,
                "rows": per_page,
                "os": (page - 1) * per_page,
                "status": "active",
                "lang_exact": "English",
            }
            response = self.get_with_retry(WB_PROCUREMENT_API, params=params)
            if not response:
                break

            try:
                data = response.json()
                notices = data.get("procurement", {})
                if isinstance(notices, dict):
                    items = list(notices.values())
                elif isinstance(notices, list):
                    items = notices
                else:
                    items = data.get("docs", data.get("results", []))

                if not items:
                    break

                all_results.extend(items)

                total = int(data.get("total", data.get("numFound", 0)))
                if page * per_page >= total:
                    break
                page += 1
            except Exception as e:
                logger.error(f"World Bank parse error: {e}")
                break

        return all_results

    def _get_region(self, country: str) -> str:
        if country in AFRICA_COUNTRIES:
            return "africa"
        if country in SEA_COUNTRIES:
            return "southeast_asia"
        return "other"

    def _parse_wb_item(self, item: dict) -> Optional[dict]:
        title = item.get("contract_desc", item.get("proj_name", item.get("noticeTitle", "")))
        if not title:
            return None

        notice_id = item.get("id", item.get("noticeId", item.get("ref_no", "")))
        tender_id = f"WB-{notice_id}" if notice_id else f"WB-{hashlib.md5(title.encode()).hexdigest()[:12]}"

        country = item.get("countryname", item.get("country_name", item.get("country", "")))
        region = self._get_region(country)

        if region == "other":
            # Only store Africa and SEA tenders
            return None

        deadline = None
        for field in ["submission_date", "close_date", "deadlineDate", "closing_date"]:
            raw = item.get(field, "")
            if raw:
                for fmt in ["%Y%m%d", "%Y-%m-%d", "%d-%b-%Y", "%Y-%m-%dT%H:%M:%SZ"]:
                    try:
                        deadline = datetime.strptime(str(raw)[:10], fmt[:len(str(raw)[:10])])
                        break
                    except ValueError:
                        continue
                if deadline:
                    break

        value = None
        raw_value = item.get("contract_amount", item.get("estimatedAmount", ""))
        if raw_value:
            try:
                value = float(str(raw_value).replace(",", "").replace("$", ""))
            except (ValueError, TypeError):
                pass

        source_url = item.get("detail_url", item.get("url", f"https://projects.worldbank.org/procurement/noticedetail?id={notice_id}"))

        ai_info = {}
        if title:
            ai_info = self.extract_tender_info(
                f"{title} {item.get('proj_name', '')} {item.get('description', '')}",
                source_url
            )

        return {
            "tender_id": tender_id,
            "title": title[:500],
            "country": country,
            "region": region,
            "buyer": item.get("org_name", item.get("borrowerName", item.get("buyer", ""))),
            "quantity_mt": ai_info.get("quantity_mt"),
            "grade_spec": ai_info.get("grade_spec"),
            "submission_deadline": deadline,
            "estimated_value_usd": value or ai_info.get("estimated_value_usd"),
            "currency": item.get("currency", ai_info.get("currency", "USD")),
            "source_url": source_url,
            "document_urls": [],
            "raw_text": str(item)[:2000],
            "status": "active",
        }
