# Neptune Bitumen Bid Aggregator

Automatically aggregates bitumen procurement tenders across **Africa**, **Southeast Asia**, and **India** for Neptune Petrochemicals Limited.

## Architecture

```
┌────────────────────────────────────────────────────┐
│  Dashboard (Next.js 14 + Tailwind)  :3000          │
│  ├─ Tender list with filters & export               │
│  ├─ Tender detail page                              │
│  └─ Alert subscription management                  │
├────────────────────────────────────────────────────┤
│  API (FastAPI)  :8000                              │
│  ├─ GET /tenders — list with filters                │
│  ├─ GET /tenders/stats                             │
│  ├─ GET /tenders/export/csv|excel                  │
│  └─ POST /alerts/subscribe                         │
├────────────────────────────────────────────────────┤
│  Crawler (Celery + Beat)                           │
│  ├─ gem_india     — GeM (gem.gov.in)               │
│  ├─ worldbank     — World Bank STEP                │
│  ├─ adb           — Asian Development Bank         │
│  └─ afdb          — AfDB + DG Market               │
├────────────────────────────────────────────────────┤
│  PostgreSQL (pgvector)  │  Redis (broker/cache)    │
└────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Prerequisites
- Docker + Docker Compose
- (Optional) Anthropic API key for AI-powered quantity/grade extraction

### 2. Setup

```bash
make setup
# Edit .env with your API keys
cp .env.example .env
nano .env
```

### 3. Start everything

```bash
make start
```

- Dashboard: http://localhost:3000
- API docs: http://localhost:8000/docs

### 4. Trigger first crawl

```bash
make crawl
```

Crawls run automatically every 6 hours via Celery Beat. Alerts are dispatched hourly.

## Data Sources

| Source | Region | Update Freq |
|--------|--------|-------------|
| GeM India (gem.gov.in) | India | Every 6h |
| World Bank STEP | Africa, SE Asia | Every 6h |
| Asian Development Bank | Southeast Asia | Every 6h |
| African Dev Bank + DG Market | Africa | Every 6h |

## Adding a New Scraper

1. Create `crawler/scrapers/my_source.py` extending `BaseScraper`
2. Implement `get_tenders() -> list[dict]`
3. Register in `crawler/tasks.py` `SCRAPERS` dict

```python
# crawler/scrapers/my_source.py
from base_scraper import BaseScraper

class MySourceScraper(BaseScraper):
    def __init__(self):
        super().__init__("my_source")

    def get_tenders(self) -> list[dict]:
        # Fetch and return tender dicts
        ...
```

## Bitumen Keywords Monitored

English: bitumen, asphalt, VG-10/30/40, PMB, CRMB, road surfacing, tack coat, prime coat, macadam, bituminous, hot mix, HMA, DBM, BC, WMM

French: bitume, asphalte, enrobé

Bahasa: aspal, perkerasan

Tamil: பிட்யூமன்

## Alert Configuration

Subscribe via the dashboard at `/alerts` or via API:

```bash
curl -X POST http://localhost:8000/alerts/subscribe \
  -H "Content-Type: application/json" \
  -d '{
    "email": "you@neptunepetro.com",
    "whatsapp": "+91xxxxxxxxxx",
    "regions": ["africa", "india"],
    "min_quantity_mt": 500
  }'
```

## Environment Variables

See `.env.example` for all required variables.
