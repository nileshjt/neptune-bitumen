"""
GlobalTenders.com scraper using Playwright for JS login.
Searches bitumen/asphalt tenders across Africa, South Asia, Southeast Asia, India.
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

SEARCH_URL = "https://www.globaltenders.com/gt-search"
SEARCH_PARAMS = (
    "tender_type=live"
    "&keyword[0]=bitumen&keyword[1]=asphalt&keyword[2]=road+surfacing"
    "&keyword[3]=bituminous&keyword[4]=PMB&keyword[5]=CRMB"
    "&notice_type=gpn,pp,spn,rei,ppn,acn,rfc"
    "&region_name[]=REG0100&region_name[]=REG0102&region_name[]=REG0103"
    "&region_name[]=REG0104&region_name[]=REG0105"
    "&region_name[]=REG0304&region_name[]=REG0305&region_name[]=IN"
)

REGION_MAP = {
    "South Africa": "africa", "Zimbabwe": "africa", "Kenya": "africa",
    "Tanzania": "africa", "Uganda": "africa", "Ethiopia": "africa",
    "Ghana": "africa", "Nigeria": "africa", "Morocco": "africa",
    "Egypt": "africa", "Senegal": "africa", "Mozambique": "africa",
    "Zambia": "africa", "Rwanda": "africa", "Angola": "africa",
    "India": "india", "Bangladesh": "south_asia", "Nepal": "south_asia",
    "Sri Lanka": "south_asia", "Pakistan": "south_asia",
    "Philippines": "southeast_asia", "Indonesia": "southeast_asia",
    "Malaysia": "southeast_asia", "Vietnam": "southeast_asia",
    "Thailand": "southeast_asia", "Myanmar": "southeast_asia",
}


class GlobalTendersScraper(BaseScraper):
    def __init__(self):
        super().__init__("globaltenders")

    def get_tenders(self) -> list[dict]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.error("Playwright not available")
            return []

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
                page.goto("https://www.globaltenders.com/login", timeout=30000)
                page.wait_for_load_state("networkidle", timeout=15000)

                # Fill login form via JS (inputs may not be accessible via Playwright selectors)
                page.wait_for_timeout(5000)
                page.evaluate("""() => {
                    const em = document.querySelector("input[name='email']");
                    const pw = document.querySelector("input[name='password']");
                    if (em) { em.value = 'bid.marketing@satgurutravel.com'; em.dispatchEvent(new Event('input', {bubbles:true})); }
                    if (pw) { pw.value = '12345678'; pw.dispatchEvent(new Event('input', {bubbles:true})); }
                }""")
                page.evaluate("""() => {
                    const btn = document.querySelector("input[name='login'], button[type='submit'], input[type='submit']");
                    if (btn) btn.click();
                }""")
                page.wait_for_load_state("networkidle", timeout=15000)

                if "login" in page.url.lower() and "dashboard" not in page.url.lower():
                    logger.warning(f"GlobalTenders: login may have failed, url={page.url}")
                else:
                    logger.info(f"GlobalTenders: logged in, url={page.url}")

                # Scrape up to 5 pages
                for pg in range(1, 6):
                    url = f"{SEARCH_URL}?{SEARCH_PARAMS}&page={pg}"
                    page.goto(url, timeout=30000)
                    page.wait_for_load_state("networkidle", timeout=15000)

                    page.wait_for_timeout(3000)
                    html = page.inner_text("body")
                    items = self._parse_text(html)
                    if not items:
                        logger.info(f"GlobalTenders page {pg}: no items, stopping")
                        break

                    for item in items:
                        tender = self._parse_item(item)
                        if tender:
                            tenders.append(tender)
                            self.save_tender(tender)

                    logger.info(f"GlobalTenders page {pg}: {len(items)} items")
                    if len(items) < 5:
                        break

            except Exception as e:
                logger.error(f"GlobalTenders Playwright error: {e}", exc_info=True)
            finally:
                browser.close()

        logger.info(f"GlobalTenders: {len(tenders)} bitumen tenders saved")
        return tenders

    def _parse_text(self, text: str) -> list[dict]:
        """Parse inner_text of GlobalTenders search results page.

        Pattern per tender block:
          View Detail
          <Title>
          Authority: <authority or 'Upgrade to view'>
          <Country>
          <publish date>
          <deadline date>
        """
        items = []
        # Split on "View Detail" separators
        blocks = [b.strip() for b in text.split("View Detail") if b.strip()]
        date_pat = re.compile(r"\d{2}\s+\w{3}\s+\d{4}|\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2}")

        for block in blocks:
            lines = [l.strip() for l in block.split("\n") if l.strip()]
            if not lines:
                continue

            # First non-empty line is the title
            title = lines[0]
            if len(title) < 20:
                continue  # skip nav/UI fragments

            country = ""
            deadline_str = ""
            authority = ""
            for line in lines[1:]:
                if line.startswith("Authority:"):
                    authority = line.replace("Authority:", "").strip()
                elif any(c.lower() in line.lower() for c in REGION_MAP.keys()):
                    for c in REGION_MAP.keys():
                        if c.lower() in line.lower():
                            country = c
                            break
                elif date_pat.match(line) and not deadline_str:
                    deadline_str = line  # first date = publish, second = deadline
                elif date_pat.match(line):
                    deadline_str = line  # overwrite with second (later) date

            items.append({
                "title": title,
                "url": SEARCH_URL,
                "raw": block[:800],
                "country": country,
                "authority": authority,
                "deadline_str": deadline_str,
            })

        return items

    def _parse_item(self, item: dict) -> Optional[dict]:
        title = item.get("title", "")
        raw = item.get("raw", "")
        if not title or not self.is_bitumen_related(title + " " + raw):
            return None

        country = item.get("country", "")
        if not country:
            for c, r in REGION_MAP.items():
                if c.lower() in raw.lower():
                    country = c
                    break
        region = REGION_MAP.get(country, "africa")

        deadline = None
        ds = item.get("deadline_str", "")
        if ds:
            for fmt in ["%d %b %Y", "%d %B %Y", "%d/%m/%Y", "%Y-%m-%d"]:
                try:
                    deadline = datetime.strptime(ds.strip()[:20], fmt)
                    break
                except ValueError:
                    continue

        tender_id = f"GT-{hashlib.md5((title + raw[:100]).encode()).hexdigest()[:12]}"
        ai_info = self.extract_tender_info(title, item.get("url", ""))

        return {
            "tender_id": tender_id,
            "title": title[:500],
            "country": country or "Unknown",
            "region": region,
            "buyer": item.get("authority", "") or ai_info.get("buyer", ""),
            "quantity_mt": ai_info.get("quantity_mt"),
            "grade_spec": ai_info.get("grade_spec"),
            "submission_deadline": deadline or ai_info.get("submission_deadline"),
            "estimated_value_usd": ai_info.get("estimated_value_usd"),
            "currency": "USD",
            "source_url": item.get("url", SEARCH_URL),
            "document_urls": [],
            "raw_text": raw[:2000],
            "status": "active",
        }
