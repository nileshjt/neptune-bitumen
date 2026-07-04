"""
World Bank Contracts API — awarded contracts with prices.
Used for price intelligence on historical bitumen/road awards.
API: search.worldbank.org/api/contractdata — no auth required.
"""
import logging
import hashlib
from datetime import datetime
from typing import Optional
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base_scraper import BaseScraper

logger = logging.getLogger(__name__)

WB_CONTRACTS_API = "https://search.worldbank.org/api/v2/contractdata"

AFRICA_COUNTRIES = {
    "Ethiopia","Kenya","Tanzania","Uganda","Rwanda","Mozambique","Zambia","Zimbabwe",
    "Ghana","Nigeria","Senegal","Cameroon","Cote d'Ivoire","Angola","Madagascar",
    "Mali","Burkina Faso","Niger","Chad","Somalia","South Sudan","Sudan","DR Congo",
    "Congo","Gabon","Botswana","Namibia","South Africa","Morocco","Algeria",
    "Tunisia","Libya","Egypt","Malawi","Lesotho","Eswatini","Djibouti","Eritrea",
    "Guinea","Sierra Leone","Liberia","Togo","Benin","Gambia",
}
SEA_COUNTRIES = {
    "Indonesia","Philippines","Vietnam","Thailand","Malaysia",
    "Myanmar","Cambodia","Lao PDR","Timor-Leste","Papua New Guinea",
}


class WorldBankContractsScraper(BaseScraper):
    """Scrapes awarded contracts — provides price intelligence."""

    def __init__(self):
        super().__init__("worldbank_contracts")

    def get_tenders(self) -> list[dict]:
        tenders = []
        keywords = ["bitumen", "asphalt", "road surfacing", "bituminous", "pavement"]

        for keyword in keywords:
            logger.info(f"Searching WB Contracts for: {keyword}")
            results = self._search_contracts(keyword)
            for item in results:
                text = f"{item.get('contract_desc','')}{item.get('proj_name','')}{item.get('majorsector_exact','')}"
                if self.is_bitumen_related(text):
                    tender = self._parse_contract(item)
                    if tender:
                        tenders.append(tender)
                        self.save_tender(tender)

        logger.info(f"WB Contracts: found {len(tenders)} bitumen awarded contracts")
        return tenders

    def _search_contracts(self, keyword: str) -> list[dict]:
        all_results = []
        page = 1
        per_page = 50

        while page <= 10:
            params = {
                "format": "json",
                "qterm": keyword,
                "rows": per_page,
                "os": (page - 1) * per_page,
                "majorsector_exact": "Transportation",
            }
            response = self.get_with_retry(WB_CONTRACTS_API, params=params)
            if not response:
                break
            try:
                data = response.json()
                contracts = data.get("contractdata", {})
                if isinstance(contracts, dict):
                    items = list(contracts.values())
                elif isinstance(contracts, list):
                    items = contracts
                else:
                    items = []

                if not items:
                    break
                all_results.extend(items)

                total = int(data.get("total", data.get("numFound", 0)))
                if page * per_page >= total:
                    break
                page += 1
            except Exception as e:
                logger.error(f"WB Contracts parse error: {e}")
                break

        return all_results

    def _get_region(self, country: str) -> Optional[str]:
        for c in AFRICA_COUNTRIES:
            if c.lower() in country.lower():
                return "africa"
        for c in SEA_COUNTRIES:
            if c.lower() in country.lower():
                return "southeast_asia"
        if "india" in country.lower():
            return "india"
        return None

    def _parse_contract(self, item: dict) -> Optional[dict]:
        title = item.get("contract_desc", item.get("proj_name", ""))
        if not title:
            return None

        country = item.get("countryname", item.get("borrower_country", ""))
        region = self._get_region(country)
        if not region:
            return None

        ref = item.get("id", item.get("contract_id", item.get("ref_no", "")))
        tender_id = f"WBC-{ref}" if ref else f"WBC-{hashlib.md5((title+country).encode()).hexdigest()[:12]}"

        # Awarded contracts have a sign date, not a deadline
        sign_date = None
        for field in ["contr_sgn_date", "contract_signing_date", "award_date"]:
            raw = item.get(field, "")
            if raw:
                for fmt in ["%Y%m%d", "%Y-%m-%d", "%d-%b-%Y"]:
                    try:
                        sign_date = datetime.strptime(str(raw)[:10], fmt)
                        break
                    except ValueError:
                        continue
                if sign_date:
                    break

        value = None
        for field in ["total_contr_amnt", "contract_amount", "contr_amnt"]:
            raw = item.get(field, "")
            if raw:
                try:
                    value = float(str(raw).replace(",", "").replace("$", ""))
                    break
                except (ValueError, TypeError):
                    pass

        supplier = item.get("supplier_name", item.get("firm_name", item.get("contractor", "")))
        buyer = item.get("org_name", item.get("borrower", item.get("buyer", "")))

        return {
            "tender_id": tender_id,
            "title": f"[AWARDED] {title[:480]}",
            "country": country,
            "region": region,
            "buyer": buyer,
            "quantity_mt": None,
            "grade_spec": None,
            "submission_deadline": sign_date,
            "estimated_value_usd": value,
            "awarded_price_usd": value,
            "currency": item.get("currency", "USD"),
            "source_url": item.get("url", f"https://projects.worldbank.org/procurement/contractdetail?id={ref}"),
            "document_urls": [],
            "raw_text": str(item)[:2000],
            "status": "awarded",
        }
