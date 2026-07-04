import logging
import hashlib
from datetime import datetime
from typing import Optional
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base_scraper import BaseScraper

logger = logging.getLogger(__name__)

AFDB_PROCUREMENT_URL = "https://www.afdb.org/en/projects-operations/procurement"
DGMARKET_URL = "https://dgmarket.com/tenders/searchTenders.do"

AFRICA_COUNTRIES = {
    "Ethiopia", "Kenya", "Tanzania", "Uganda", "Rwanda", "Mozambique",
    "Zambia", "Zimbabwe", "Ghana", "Nigeria", "Senegal", "Cameroon",
    "Côte d'Ivoire", "Ivory Coast", "Angola", "Madagascar", "Mali",
    "Burkina Faso", "Niger", "Chad", "Somalia", "South Sudan", "Sudan",
    "DR Congo", "DRC", "Congo", "Gabon", "Botswana", "Namibia",
    "South Africa", "Morocco", "Algeria", "Tunisia", "Libya", "Egypt",
    "Malawi", "Lesotho", "Swaziland", "Eswatini", "Djibouti", "Eritrea",
    "Guinea", "Sierra Leone", "Liberia", "Togo", "Benin", "Gambia",
}


class AfDBScraper(BaseScraper):
    def __init__(self):
        super().__init__("afdb")
        self.base_url = "https://www.afdb.org"

    def get_tenders(self) -> list[dict]:
        tenders = []
        results = []

        # Try AfDB website
        logger.info("Searching AfDB procurement portal")
        results.extend(self._search_afdb())

        # Try DG Market as aggregator for Africa
        logger.info("Searching DG Market for Africa bitumen tenders")
        results.extend(self._search_dgmarket())

        for item in results:
            text = f"{item.get('title', '')} {item.get('description', '')} {item.get('sector', '')}"
            if self.is_bitumen_related(text):
                tender = self._parse_item(item)
                if tender:
                    tenders.append(tender)
                    self.save_tender(tender)

        logger.info(f"AfDB/Africa: found {len(tenders)} bitumen tenders")
        return tenders

    def _search_afdb(self) -> list[dict]:
        """Scrape AfDB procurement page."""
        from bs4 import BeautifulSoup
        items = []

        for keyword in ["bitumen", "asphalt", "road surfacing"]:
            params = {
                "q": keyword,
                "type": "procurement",
                "sector": "transport",
            }
            response = self.get_with_retry(
                f"{self.base_url}/en/search",
                params=params,
            )
            if not response:
                continue

            try:
                soup = BeautifulSoup(response.text, "lxml")
                for result in soup.select(".search-result, .views-row, article.node"):
                    title_el = result.select_one("h3 a, h2 a, .title a, a.title")
                    date_el = result.select_one(".date, time, .field-date")
                    country_el = result.select_one(".country, .field-country")

                    if not title_el:
                        continue

                    href = title_el.get("href", "")
                    if href and not href.startswith("http"):
                        href = f"{self.base_url}{href}"

                    items.append({
                        "title": title_el.get_text(strip=True),
                        "country": country_el.get_text(strip=True) if country_el else "",
                        "deadline_text": date_el.get_text(strip=True) if date_el else "",
                        "url": href,
                        "source": "afdb",
                    })
            except Exception as e:
                logger.error(f"AfDB parse error: {e}")

        return items

    def _search_dgmarket(self) -> list[dict]:
        """Search DG Market aggregator for Africa bitumen tenders."""
        from bs4 import BeautifulSoup
        items = []

        for keyword in ["bitumen", "asphalt"]:
            params = {
                "region": "Africa",
                "q": keyword,
                "status": "active",
                "language": "en",
            }
            response = self.get_with_retry(DGMARKET_URL, params=params)
            if not response:
                continue

            try:
                if "application/json" in response.headers.get("content-type", ""):
                    data = response.json()
                    for item in data.get("tenders", data.get("results", [])):
                        items.append({
                            "title": item.get("title", ""),
                            "country": item.get("country", ""),
                            "deadline_text": item.get("deadline", ""),
                            "estimated_value": item.get("value", ""),
                            "url": item.get("url", ""),
                            "buyer": item.get("buyer", ""),
                            "source": "dgmarket",
                        })
                else:
                    soup = BeautifulSoup(response.text, "lxml")
                    for row in soup.select("table.tenders tr, .tender-item, .result-item"):
                        cells = row.find_all("td")
                        if len(cells) >= 3:
                            title_el = cells[0].find("a") or cells[1].find("a")
                            if title_el:
                                items.append({
                                    "title": title_el.get_text(strip=True),
                                    "country": cells[2].get_text(strip=True) if len(cells) > 2 else "",
                                    "deadline_text": cells[-1].get_text(strip=True),
                                    "url": title_el.get("href", ""),
                                    "source": "dgmarket",
                                })
            except Exception as e:
                logger.error(f"DG Market error for '{keyword}': {e}")

        return items

    def _parse_item(self, item: dict) -> Optional[dict]:
        title = item.get("title", "")
        if not title:
            return None

        country = item.get("country", "")
        if country and not any(c.lower() in country.lower() for c in AFRICA_COUNTRIES):
            return None

        source = item.get("source", "afdb")
        ref = item.get("id", item.get("ref", ""))
        tender_id = f"AFDB-{ref}" if ref else f"AFDB-{hashlib.md5((title + country).encode()).hexdigest()[:12]}"

        deadline = None
        raw = item.get("deadline_text", item.get("deadline", ""))
        if raw:
            for fmt in ["%d %b %Y", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"]:
                try:
                    deadline = datetime.strptime(str(raw).strip()[:20], fmt)
                    break
                except ValueError:
                    continue

        value = None
        raw_val = item.get("estimated_value", item.get("value", ""))
        if raw_val:
            try:
                value = float(str(raw_val).replace(",", "").replace("$", "").replace("USD", "").strip())
            except (ValueError, TypeError):
                pass

        source_url = item.get("url", "")
        ai_info = self.extract_tender_info(
            f"{title} {item.get('description', '')}",
            source_url or f"https://www.afdb.org/en/projects-operations/procurement",
        )

        return {
            "tender_id": tender_id,
            "title": title[:500],
            "country": country,
            "region": "africa",
            "buyer": item.get("buyer", item.get("agency", "AfDB Project")),
            "quantity_mt": ai_info.get("quantity_mt"),
            "grade_spec": ai_info.get("grade_spec"),
            "submission_deadline": deadline or ai_info.get("submission_deadline"),
            "estimated_value_usd": value or ai_info.get("estimated_value_usd"),
            "currency": item.get("currency", ai_info.get("currency", "USD")),
            "source_url": source_url or "https://www.afdb.org/en/projects-operations/procurement",
            "document_urls": [],
            "raw_text": str(item)[:2000],
            "status": "active",
        }
