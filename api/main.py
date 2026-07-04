from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base
from routers import tenders, alerts

# Create tables on startup (for dev; use Alembic migrations in prod)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Neptune Bitumen Bid Aggregator API",
    description="Aggregates bitumen procurement tenders across Africa, Southeast Asia, and India",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tenders.router)
app.include_router(alerts.router)


@app.get("/health")
def health():
    return {"status": "ok"}
