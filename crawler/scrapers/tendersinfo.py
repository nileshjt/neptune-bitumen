"""
TendersInfo.net scraper using Playwright for JS login.
Uses AI search: /TenderAI/TenderAIList?searchtext=bitumen-tenders
Filters to Africa, South Asia, Southeast Asia, India.
"""
import logging
import hashlib
import re
from datetime import datetime
from typing import Optional
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base_scraper import BaseScraper
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://www.tendersinfo.net"
LOGIN_URL = "https://www.tendersinfo.com/login"
SEARCH_URL = f"{BASE_URL}/TenderAI/TenderAIList"

TARGET_COUNTRIES = {
    "South Africa", "Zimbabwe", "Kenya", "Tanzania", "Uganda", "Ethiopia",
    "Ghana", "Nigeria", "Morocco", "Egypt", "Senegal", "Mozambique",
    "Zambia", "Rwanda", "Cameroon", "Angola",
    "India", "Bangladesh", "Nepal", "Sri Lanka", "Pakistan",
    "Philippines", "Indonesia", "Malaysia", "Vietnam", "Thailand", "Myanmar",
    "Oman", "Saudi Arabia", "UAE", "Qatar", "Kuwait",
}

REGION_MAP = {
    "South Africa": "africa", "Zimbabwe": "africa", "Kenya": "africa",
    "Tanzania": "africa", "Uganda": "africa", "Ethiopia": "africa",
    "Ghana": "africa", "Nigeria": "africa", "Morocco": "africa",
    "Egypt": "africa", "Senegal": "africa", "Mozambique": "africa",
    "India": "india", "Bangladesh": "south_asia", "Nepal": "south_asia",
    "Sri Lanka": "south_asia", "Pakistan": "south_asia",
    "Philippines": "southeast_asia", "Indonesia": "southeast_asia",
    "Malaysia": "southeast_asia", "Vietnam": "southeast_asia",
    "Thailand": "southeast_asia", "Myanmar": "southeast_asia",
}

SEARCH_QUERIES = ["bitumen-tenders", "asphalt-tenders", "road-bitumen-tenders"]


class TendersInfoScraper(BaseScraper):
    def __init__(self):
        super().__init__("tendersinfo")

    def get_tenders(self) -> list[dict]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.error("Playwright not available")
            return []

        seen_ids = set()
        tenders = []

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            ctx = browser.new_context(user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ))
            page = ctx.new_page()

            try:
                # Login
                page.goto(LOGIN_URL, timeout=30000)
                page.wait_for_load_state("networkidle", timeout=15000)

                page.fill("input[placeholder*='User ID'], input[name*='userid'], input[name*='email'], input[type='text']",
                          "bid.marketing@satgurutravel.com")
                page.fill("input[type='password']", "Qdhdu@d45464AKkhj")
                page.click("button[type='submit'], input[type='submit'], .btn-primary")
                page.wait_for_load_state("networkidle", timeout=20000)

                logger.info(f"TendersInfo: after login url={page.url}")

                for query in SEARCH_QUERIES:
                    page.goto(f"{SEARCH_URL}?searchtext={query}", timeout=30000)
                    page.wait_for_load_state("networkidle", timeout=20000)
                    page.wait_for_timeout(6000)  # JS renders results after networkidle

                    html = page.inner_text("body")
                    items = self._parse_html(html)
                    logger.info(f"TendersInfo '{query}': {len(items)} items parsed")

                    for item in items:
                        tid = item.get("tid", "")
                        if tid in seen_ids:
                            continue
                        if tid:
                            seen_ids.add(tid)

                        country = item.get("country", "")
                        if country and not any(c in country for c in TARGET_COUNTRIES):
                            continue

                        # Try to download the tender document from detail page
                        if tid:
                            doc_url = self._download_tender_doc(page, ctx, tid)
                            if doc_url:
                                item["document_urls"] = [doc_url]

                        tender = self._to_tender(item)
                        if tender:
                            tenders.append(tender)
                            self.save_tender(tender)

            except Exception as e:
                logger.error(f"TendersInfo Playwright error: {e}", exc_info=True)
            finally:
                browser.close()

        logger.info(f"TendersInfo: {len(tenders)} target-country bitumen tenders saved")
        return tenders

    def _download_tender_doc(self, page, ctx, tid: str) -> Optional[str]:
        """Visit detail page, download tender document, upload to GCS, return public URL."""
        import tempfile, os
        detail_url = f"{BASE_URL}/Tender/TenderDetail/{tid}"
        detail_page = ctx.new_page()
        try:
            detail_page.goto(detail_url, timeout=30000)
            detail_page.wait_for_load_state("networkidle", timeout=15000)
            detail_page.wait_for_timeout(3000)

            # Look for a download link/button
            # TendersInfo typically has a "Download" button or a PDF link
            download_el = detail_page.query_selector(
                "a[href*='download'], a[href*='.pdf'], a[href*='.zip'], "
                "button:has-text('Download'), a:has-text('Download Document'), "
                "a:has-text('Download'), a:has-text('Attachment')"
            )

            if not download_el:
                logger.info(f"TendersInfo TID {tid}: no download button found")
                return None

            href = download_el.get_attribute("href") or ""

            if href and (href.endswith(".pdf") or href.endswith(".zip") or "download" in href.lower()):
                # Direct URL — download using httpx with session cookies
                if not href.startswith("http"):
                    href = BASE_URL + href if href.startswith("/") else BASE_URL + "/" + href
                cookies = {c["name"]: c["value"] for c in ctx.cookies()}
                resp = self.client.get(href, headers={"Referer": detail_url}, cookies=cookies, timeout=60.0)
                if resp.status_code == 200 and len(resp.content) > 1000:
                    ext = ".pdf" if "pdf" in resp.headers.get("content-type", "") else os.path.splitext(href)[1] or ".pdf"
                    filename = f"TI-{tid}{ext}"
                    return self.upload_to_gcs(resp.content, filename, resp.headers.get("content-type", "application/pdf"))
            else:
                # Use Playwright download handler
                with detail_page.expect_download(timeout=30000) as dl_info:
                    download_el.click()
                dl = dl_info.value
                with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(dl.suggested_filename)[1] or ".pdf") as tmp:
                    dl.save_as(tmp.name)
                    with open(tmp.name, "rb") as f:
                        file_bytes = f.read()
                os.unlink(tmp.name)
                if len(file_bytes) > 1000:
                    filename = f"TI-{tid}{os.path.splitext(dl.suggested_filename)[1] or '.pdf'}"
                    return self.upload_to_gcs(file_bytes, filename)

        except Exception as e:
            logger.warning(f"TendersInfo doc download failed for TID {tid}: {e}")
        finally:
            detail_page.close()
        return None

    def _parse_html(self, html: str) -> list[dict]:
        items = []
        # html is already plain text from inner_text("body")
        raw_text = html
        blocks = re.split(r"(?=TID:\d{7,})", raw_text)

        for block in blocks:
            if not block.strip():
                continue
            tid_match = re.search(r"TID:(\d+)", block)
            if not tid_match:
                continue

            tid = tid_match.group(1)
            lines = [l.strip() for l in block.split("\n") if l.strip()]
            # first_line contains "TID:NNNN <country/org> ..." — skip TID prefix for title search
            first_line = lines[0] if lines else ""
            title = ""
            for line in lines[1:5]:
                # Skip metadata lines
                if any(skip in line for skip in ["Worth", "EMD", "Publish", "Due Date", "Days to go", "%", "TID:"]):
                    continue
                if len(line) > 15:
                    title = line
                    break
            if not title:
                # Strip TID prefix from first_line
                title = re.sub(r"^TID:\d+\s*", "", first_line).strip()

            country = ""
            for c in TARGET_COUNTRIES:
                if c.lower() in first_line.lower() or c.lower() in (lines[1] if len(lines) > 1 else "").lower():
                    country = c
                    break

            worth_match = re.search(r"Worth\s*:\s*([^\n]+)", block)
            worth = worth_match.group(1).strip() if worth_match else ""

            due_match = re.search(r"Due Date\s*:(\d{2}\s+\w+\s+\d{4})", block)
            due_date = due_match.group(1).strip() if due_match else ""

            items.append({
                "tid": tid,
                "title": title,
                "country": country,
                "worth": worth,
                "due_date": due_date,
                "raw": block[:2000],
                "url": f"{BASE_URL}/Tender/TenderDetail/{tid}",
            })

        return items

    def _parse_date(self, s: str) -> Optional[datetime]:
        for fmt in ["%d %B %Y", "%d %b %Y", "%Y-%m-%d", "%d/%m/%Y"]:
            try:
                return datetime.strptime(s.strip()[:20], fmt)
            except ValueError:
                continue
        return None

    def _parse_value(self, worth: str) -> Optional[float]:
        if not worth or "Refer" in worth:
            return None
        m = re.search(r"[\d,]+(?:\.\d+)?", worth.replace(",", ""))
        if not m:
            return None
        try:
            val = float(m.group().replace(",", ""))
            if "Lac" in worth:
                val *= 100000
            if "INR" in worth or "Lac" in worth:
                val /= 84
            elif "EUR" in worth:
                val *= 1.08
            elif "GBP" in worth:
                val *= 1.27
            return val
        except (ValueError, ZeroDivisionError):
            return None

    def _to_tender(self, item: dict) -> Optional[dict]:
        title = item.get("title", "")
        raw = item.get("raw", "")
        if not title or not self.is_bitumen_related(title + " " + raw):
            return None

        country = item.get("country", "Unknown")
        region = REGION_MAP.get(country, "africa")

        tid = item.get("tid", "")
        tender_id = f"TI-{tid}" if tid else f"TI-{hashlib.md5(title.encode()).hexdigest()[:12]}"
        ai_info = self.extract_tender_info(title, item.get("url", ""))

        return {
            "tender_id": tender_id,
            "title": title[:500],
            "country": country,
            "region": region,
            "buyer": ai_info.get("buyer", ""),
            "quantity_mt": ai_info.get("quantity_mt"),
            "grade_spec": ai_info.get("grade_spec"),
            "submission_deadline": self._parse_date(item.get("due_date", "")) or ai_info.get("submission_deadline"),
            "estimated_value_usd": self._parse_value(item.get("worth", "")) or ai_info.get("estimated_value_usd"),
            "currency": "USD",
            "source_url": item.get("url", SEARCH_URL),
            "document_urls": item.get("document_urls", []),
            "raw_text": raw[:2000],
            "status": "active",
        }
