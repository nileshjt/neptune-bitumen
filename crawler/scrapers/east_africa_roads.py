"""
East Africa Road Agencies — direct portal scrapers
Covers: KENHA (Kenya), KeRRA (Kenya Rural Roads), TANROADS (Tanzania),
        UNRA (Uganda), ERA (Ethiopia Roads Authority)
"""
import logging
import hashlib
from datetime import datetime
from typing import Optional
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base_scraper import BaseScraper

logger = logging.getLogger(__name__)

AGENCIES = [
    {
        "name": "KENHA",
        "country": "Kenya",
        "url": "https://www.kenha.co.ke/index.php/tenders",
        "awarded_url": "https://www.kenha.co.ke/index.php/awarded-tenders",
    },
    {
        "name": "KeRRA",
        "country": "Kenya",
        "url": "https://www.kerra.go.ke/tenders",
        "awarded_url": "https://www.kerra.go.ke/awarded-tenders",
    },
    {
        "name": "TANROADS",
        "country": "Tanzania",
        "url": "https://www.tanroads.go.tz/tenders",
        "awarded_url": "https://www.tanroads.go.tz/awarded-contracts",
    },
    {
        "name": "UNRA",
        "country": "Uganda",
        "url": "https://www.unra.go.ug/tenders",
        "awarded_url": "https://www.unra.go.ug/awarded-contracts",
    },
    {
        "name": "ERA Ethiopia",
        "country": "Ethiopia",
        "url": "https://www.era.gov.et/tenders",
        "awarded_url": None,
    },
]


class EastAfricaRoadsScraper(BaseScraper):
    def __init__(self):
        super().__init__("east_africa_roads")

    def get_tenders(self) -> list[dict]:
        tenders = []

        for agency in AGENCIES:
            logger.info(f"Scraping {agency['name']} ({agency['country']})")
            # Active tenders
            items = self._scrape_agency(agency, awarded=False)
            for item in items:
                text = f"{item.get('title','')} {item.get('description','')}"
                if self.is_bitumen_related(text):
                    tender = self._parse_item(item, agency, awarded=False)
                    if tender:
                        tenders.append(tender)
                        self.save_tender(tender)

            # Awarded contracts (price intelligence)
            if agency.get("awarded_url"):
                awarded = self._scrape_agency(agency, awarded=True)
                for item in awarded:
                    text = f"{item.get('title','')} {item.get('description','')}"
                    if self.is_bitumen_related(text):
                        tender = self._parse_item(item, agency, awarded=True)
                        if tender:
                            tenders.append(tender)
                            self.save_tender(tender)

        logger.info(f"East Africa Roads: found {len(tenders)} tenders")
        return tenders

    def _is_road_related(self, text: str) -> bool:
        road_kw = ["road", "highway", "surfacing", "pavement", "tarmac", "overlay", "rehabilitation"]
        return any(kw in text.lower() for kw in road_kw)

    def _scrape_agency(self, agency: dict, awarded: bool) -> list[dict]:
        from bs4 import BeautifulSoup
        items = []
        url = agency["awarded_url"] if awarded else agency["url"]
        if not url:
            return []

        response = self.get_with_retry(url)
        if not response:
            logger.warning(f"{agency['name']}: no response from {url}")
            return []

        try:
            soup = BeautifulSoup(response.text, "lxml")

            # Try JSON first (some agencies use REST APIs)
            if "application/json" in response.headers.get("content-type", ""):
                data = response.json()
                return data if isinstance(data, list) else data.get("tenders", data.get("data", []))

            # Parse HTML tender tables/lists
            # Pattern 1: table rows
            for table in soup.find_all("table"):
                rows = table.find_all("tr")[1:]
                for row in rows:
                    cells = row.find_all("td")
                    if len(cells) < 2:
                        continue
                    link = row.find("a")
                    title = link.get_text(strip=True) if link else cells[0].get_text(strip=True)
                    if not title or len(title) < 10:
                        continue
                    href = link["href"] if link and link.get("href") else ""
                    if href and not href.startswith("http"):
                        base = url.rsplit("/", 1)[0]
                        href = f"{base}/{href.lstrip('/')}"

                    ref = cells[0].get_text(strip=True) if len(cells) > 0 else ""
                    deadline = cells[-2].get_text(strip=True) if len(cells) > 3 else ""
                    value = ""
                    for cell in cells:
                        text_c = cell.get_text(strip=True)
                        if any(c in text_c for c in ["$", "USD", "KES", "TZS", "UGX", "ETB"]):
                            value = text_c
                            break

                    items.append({
                        "title": title,
                        "ref": ref,
                        "deadline_text": deadline,
                        "value_text": value,
                        "url": href or url,
                    })

            # Pattern 2: list items / article cards
            if not items:
                for el in soup.select("article, .tender-item, .tender-row, li.tender, .views-row"):
                    title_el = el.select_one("h2, h3, h4, .title, a")
                    if not title_el:
                        continue
                    title = title_el.get_text(strip=True)
                    href = title_el.get("href", "") if title_el.name == "a" else ""
                    if not href:
                        a = el.find("a")
                        href = a["href"] if a else ""
                    if href and not href.startswith("http"):
                        base = url.rsplit("/", 1)[0]
                        href = f"{base}/{href.lstrip('/')}"

                    date_el = el.select_one(".date, time, .deadline, .closing")
                    items.append({
                        "title": title,
                        "ref": "",
                        "deadline_text": date_el.get_text(strip=True) if date_el else "",
                        "value_text": "",
                        "url": href or url,
                    })

        except Exception as e:
            logger.error(f"{agency['name']} parse error: {e}")

        return items

    def _parse_item(self, item: dict, agency: dict, awarded: bool) -> Optional[dict]:
        title = item.get("title", "")
        if not title:
            return None

        ref = item.get("ref", "")
        prefix = "AWD" if awarded else "TND"
        tender_id = f"{agency['name']}-{prefix}-{ref}" if ref else \
                    f"{agency['name']}-{prefix}-{hashlib.md5(title.encode()).hexdigest()[:12]}"

        deadline = None
        raw = item.get("deadline_text", "")
        if raw:
            for fmt in ["%d %B %Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%b-%Y", "%B %d, %Y"]:
                try:
                    deadline = datetime.strptime(raw.strip()[:20], fmt)
                    break
                except ValueError:
                    continue

        value = None
        raw_val = item.get("value_text", "")
        if raw_val:
            import re
            nums = re.findall(r"[\d,]+(?:\.\d+)?", raw_val.replace(",", ""))
            if nums:
                try:
                    value = float(nums[0])
                    # Convert local currency to USD approx
                    if "KES" in raw_val or "Ksh" in raw_val:
                        value /= 130
                    elif "TZS" in raw_val:
                        value /= 2500
                    elif "UGX" in raw_val:
                        value /= 3700
                    elif "ETB" in raw_val:
                        value /= 57
                except (ValueError, TypeError):
                    pass

        source_url = item.get("url", agency["url"])
        ai_info = self.extract_tender_info(f"{title}", source_url)

        return {
            "tender_id": tender_id,
            "title": (("[AWARDED] " if awarded else "") + title)[:500],
            "country": agency["country"],
            "region": "africa",
            "buyer": agency["name"],
            "quantity_mt": ai_info.get("quantity_mt"),
            "grade_spec": ai_info.get("grade_spec"),
            "submission_deadline": deadline or ai_info.get("submission_deadline"),
            "estimated_value_usd": value or ai_info.get("estimated_value_usd"),
            "awarded_price_usd": value if awarded else None,
            "currency": {"Kenya": "KES", "Tanzania": "TZS", "Uganda": "UGX", "Ethiopia": "ETB"}.get(agency["country"], "USD"),
            "source_url": source_url,
            "document_urls": [],
            "raw_text": str(item)[:2000],
            "status": "awarded" if awarded else "active",
        }
