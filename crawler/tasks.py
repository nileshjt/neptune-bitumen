import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
from datetime import datetime
from celery import Celery
from celery.schedules import crontab
from config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND
from models import Base, CrawlLog
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from config import DATABASE_URL

logger = logging.getLogger(__name__)

app = Celery("neptune_crawler", broker=CELERY_BROKER_URL, backend=CELERY_RESULT_BACKEND)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
)

app.conf.beat_schedule = {
    "crawl-all-sources": {
        "task": "tasks.crawl_all",
        "schedule": crontab(minute=0, hour="*/6"),
    },
    "send-alerts": {
        "task": "tasks.send_alerts",
        "schedule": crontab(minute=30, hour="*/1"),
    },
}

engine = create_engine(DATABASE_URL)

SCRAPERS = {
    # India
    "gem_india": "scrapers.gem_india.GeMIndiaScraper",
    "cppp_india": "scrapers.cppp_india.CPPPIndiaScraper",
    # Global MDBs
    "worldbank": "scrapers.worldbank.WorldBankScraper",
    "worldbank_contracts": "scrapers.worldbank_contracts.WorldBankContractsScraper",
    "adb": "scrapers.adb.ADBScraper",
    "afdb": "scrapers.afdb.AfDBScraper",
    # Southeast Asia
    "philgeps": "scrapers.philgeps.PhilGEPSScraper",
    "lpse_indonesia": "scrapers.lpse_indonesia.LPSEIndonesiaScraper",
    # East Africa
    "east_africa_roads": "scrapers.east_africa_roads.EastAfricaRoadsScraper",
    # Paid portals
    "globaltenders": "scrapers.globaltenders.GlobalTendersScraper",
    "tendersinfo": "scrapers.tendersinfo.TendersInfoScraper",
}


def _get_scraper(scraper_class_path: str):
    """Dynamically import and instantiate a scraper class."""
    module_path, class_name = scraper_class_path.rsplit(".", 1)
    import importlib
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    return cls()


@app.task(bind=True, name="tasks.crawl_source", max_retries=2)
def crawl_source(self, source_name: str):
    """Run a single crawler and log results."""
    if source_name not in SCRAPERS:
        logger.error(f"Unknown source: {source_name}")
        return {"source": source_name, "error": "Unknown source"}

    log = CrawlLog(source_name=source_name, started_at=datetime.utcnow())
    with Session(engine) as session:
        session.add(log)
        session.commit()
        log_id = log.id

    tenders_found = 0
    error_msg = None

    try:
        scraper = _get_scraper(SCRAPERS[source_name])
        tenders = scraper.get_tenders()
        tenders_found = len(tenders)
        scraper.close()
        logger.info(f"[{source_name}] Crawl complete: {tenders_found} tenders")
    except Exception as e:
        error_msg = str(e)
        logger.error(f"[{source_name}] Crawl failed: {e}", exc_info=True)
        try:
            raise self.retry(exc=e, countdown=60)
        except self.MaxRetriesExceededError:
            pass

    with Session(engine) as session:
        log = session.get(CrawlLog, log_id)
        if log:
            log.finished_at = datetime.utcnow()
            log.tenders_found = tenders_found
            log.errors = error_msg
            session.commit()

    return {"source": source_name, "tenders_found": tenders_found, "error": error_msg}


@app.task(name="tasks.crawl_all")
def crawl_all():
    """Fan out to all configured scrapers."""
    results = []
    for source_name in SCRAPERS.keys():
        result = crawl_source.delay(source_name)
        results.append({"source": source_name, "task_id": result.id})
    logger.info(f"Launched {len(results)} crawl tasks")
    return results


@app.task(name="tasks.send_alerts")
def send_alerts():
    """Find new unnotified tenders and dispatch alerts."""
    from alerts import check_and_send_alerts
    sent = check_and_send_alerts()
    logger.info(f"Alerts sent: {sent}")
    return {"alerts_sent": sent}
