"""
Indonesia LPSE — Layanan Pengadaan Secara Elektronik
National federated procurement system with 500+ local portals.
Key portal: lpse.pu.go.id (Ministry of Public Works / Kementerian PUPR)
Also covers: lpse.kemenhub.go.id (transport), lpse.bpjt.go.id (toll roads)
LPSE portals expose a JSON API used by their own frontend.
"""
import logging
import hashlib
from datetime import datetime
from typing import Optional
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base_scraper import BaseScraper

logger = logging.getLogger(__name__)

# Primary LPSE portals for road/bitumen procurement
LPSE_PORTALS = [
    {"name": "PUPR", "base": "https://lpse.pu.go.id",       "org": "Kementerian PUPR (Public Works)"},
    {"name": "BPJT", "base": "https://lpse.bpjt.go.id",     "org": "BPJT (Toll Roads Authority)"},
    {"name": "Bina Marga", "base": "https://lpse.binamarga.go.id", "org": "Ditjen Bina Marga"},
]

LPSE_TENDER_API = "/eproc4/dt/lelang"
KEYWORDS_ID = ["aspal", "bitumen", "perkerasan", "hotmix", "asphalt", "laston", "latasir", "beton aspal"]


class LPSEIndonesiaScraper(BaseScraper):
    def __init__(self):
        super().__init__("lpse_indonesia")

    def get_tenders(self) -> list[dict]:
        tenders = []

        for portal in LPSE_PORTALS:
            logger.info(f"Searching LPSE {portal['name']}")
            for keyword in KEYWORDS_ID:
                results = self._search_lpse(portal, keyword)
                for item in results:
                    text = f"{item.get('namaPaket','')} {item.get('namaLelang','')}"
                    if self.is_bitumen_related(text) or any(k in text.lower() for k in KEYWORDS_ID):
                        tender = self._parse_item(item, portal)
                        if tender:
                            tenders.append(tender)
                            self.save_tender(tender)

        logger.info(f"LPSE Indonesia: found {len(tenders)} bitumen tenders")
        return tenders

    def _search_lpse(self, portal: dict, keyword: str) -> list[dict]:
        """LPSE portals expose a DataTables JSON API."""
        all_items = []
        start = 0
        length = 50

        while start < 200:  # max 4 pages per keyword per portal
            params = {
                "draw": 1,
                "start": start,
                "length": length,
                "search[value]": keyword,
                "search[regex]": "false",
                "idKategori": "0",  # all categories
                "statusPaket": "1",  # active
            }
            url = f"{portal['base']}{LPSE_TENDER_API}"
            response = self.get_with_retry(url, params=params)
            if not response:
                break

            try:
                data = response.json()
                items = data.get("data", data.get("aaData", []))
                if not items:
                    break
                all_items.extend(items)

                total = data.get("recordsTotal", data.get("iTotalRecords", 0))
                start += length
                if start >= total:
                    break
            except Exception as e:
                logger.error(f"LPSE {portal['name']} parse error: {e}")
                # Try HTML fallback
                return self._scrape_lpse_html(portal, keyword)

        return all_items

    def _scrape_lpse_html(self, portal: dict, keyword: str) -> list[dict]:
        from bs4 import BeautifulSoup
        items = []
        try:
            response = self.get_with_retry(
                f"{portal['base']}/eproc4/lelang",
                params={"search[value]": keyword}
            )
            if not response:
                return []
            soup = BeautifulSoup(response.text, "lxml")
            for row in soup.select("table tbody tr, .paket-row"):
                cells = row.find_all("td")
                if len(cells) < 3:
                    continue
                link = row.find("a")
                items.append({
                    "namaPaket": link.get_text(strip=True) if link else cells[1].get_text(strip=True),
                    "url": link["href"] if link and link.get("href") else "",
                    "satker": cells[2].get_text(strip=True) if len(cells) > 2 else portal["org"],
                    "hps": cells[-2].get_text(strip=True) if len(cells) > 4 else "",
                    "deadline": cells[-1].get_text(strip=True) if cells else "",
                })
        except Exception as e:
            logger.error(f"LPSE HTML scrape error: {e}")
        return items

    def _parse_item(self, item: dict, portal: dict) -> Optional[dict]:
        # LPSE JSON field names vary — try common ones
        title = (
            item.get("namaPaket") or item.get("namaLelang") or
            item.get("nama_paket") or (item[1] if isinstance(item, list) and len(item) > 1 else "")
        )
        if not title:
            return None

        ref = (
            item.get("kodeRup") or item.get("idLelang") or
            item.get("kode_rup") or ""
        )
        tender_id = f"LPSE-{portal['name']}-{ref}" if ref else f"LPSE-{hashlib.md5((title+portal['name']).encode()).hexdigest()[:12]}"

        # Parse deadline
        deadline = None
        raw = item.get("tanggalPemasukan") or item.get("batasPenawaran") or item.get("deadline", "")
        if raw:
            for fmt in ["%Y-%m-%dT%H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y", "%Y-%m-%d"]:
                try:
                    deadline = datetime.strptime(str(raw).strip()[:19], fmt)
                    break
                except ValueError:
                    continue

        # Parse value (HPS = Harga Perkiraan Sendiri = owner's estimated price)
        value_idr = None
        for field in ["hps", "nilaiHps", "nilai_hps", "paguAnggaran"]:
            raw_val = item.get(field, "")
            if raw_val:
                try:
                    value_idr = float(str(raw_val).replace(",", "").replace(".", "").replace("Rp", "").strip())
                    break
                except (ValueError, TypeError):
                    pass

        # Convert IDR to USD (approx)
        value_usd = value_idr / 16000 if value_idr else None

        buyer = item.get("satker") or item.get("namaSatker") or portal["org"]

        href = item.get("url", item.get("detailUrl", ""))
        if href and not href.startswith("http"):
            href = f"{portal['base']}{href}"
        if not href:
            href = f"{portal['base']}/eproc4/lelang"

        ai_info = self.extract_tender_info(f"{title} {buyer}", href)

        return {
            "tender_id": tender_id,
            "title": str(title)[:500],
            "country": "Indonesia",
            "region": "southeast_asia",
            "buyer": str(buyer)[:500],
            "quantity_mt": ai_info.get("quantity_mt"),
            "grade_spec": ai_info.get("grade_spec"),
            "submission_deadline": deadline,
            "estimated_value_usd": value_usd or ai_info.get("estimated_value_usd"),
            "currency": "IDR",
            "source_url": href,
            "document_urls": [],
            "raw_text": str(item)[:2000],
            "status": "active",
        }
