"""
Job Listings MCP Server — FastAPI Application

Endpoints:
  GET  /          → Health check + stats
  GET  /jobs      → Query job listings (with ?location=, ?keyword=, ?hours= filters)
  POST /scrape    → Manually trigger a scrape run
  GET  /status    → Last scrape status

Scheduler:
  APScheduler runs `scrape_all_roles()` every SCRAPE_INTERVAL_HOURS.
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

import uvicorn
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import ALLOWED_ORIGINS, HOST, PORT, ROLE_TIERS, SCRAPE_INTERVAL_HOURS
from database import count_jobs, init_db, query_jobs
from scraper import scrape_all_roles

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-12s | %(levelname)-7s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main")

_last_scrape: dict[str, Any] = {"status": "pending", "message": "No scrape has run yet."}


def _run_scrape() -> None:
    """Wrapper called by the scheduler."""
    global _last_scrape
    logger.info("⏰ Scheduled scrape triggered")

    try:
        summary = scrape_all_roles()
        _last_scrape = {
            "status": "success",
            "summary": summary,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Scrape failed: {e}", exc_info=True)
        _last_scrape = {
            "status": "error",
            "error": str(e),
            "failed_at": datetime.now(timezone.utc).isoformat(),
        }


scheduler = BackgroundScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize DB, start scheduler, and run initial scrape on startup."""
    logger.info("🚀 Starting Job Listings MCP Server")

    init_db()
    logger.info("📦 Database initialized")

    import threading

    initial_scrape = threading.Thread(target=_run_scrape, daemon=True)
    initial_scrape.start()
    logger.info("🔍 Initial scrape started in background")

    scheduler.add_job(
        _run_scrape,
        trigger=IntervalTrigger(hours=SCRAPE_INTERVAL_HOURS),
        id="periodic_scrape",
        name=f"Scrape jobs every {SCRAPE_INTERVAL_HOURS}h",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(f"⏰ Scheduler started — interval: {SCRAPE_INTERVAL_HOURS}h")

    yield

    scheduler.shutdown(wait=False)
    logger.info("🛑 Scheduler shut down")


app = FastAPI(
    title="Job Listings MCP Server",
    description="Scrapes and serves fresh job listings for the portfolio live feed.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/", tags=["Health"])
async def health_check():
    """Health check with basic stats."""
    total = count_jobs()
    return {
        "status": "healthy",
        "service": "Job Listings MCP Server",
        "total_jobs_in_db": total,
        "scrape_interval_hours": SCRAPE_INTERVAL_HOURS,
        "role_tiers": list(ROLE_TIERS.keys()),
    }


@app.get("/jobs", tags=["Jobs"])
async def get_jobs(
    location: str | None = Query(None, description="Filter by location (substring match)"),
    keyword: str | None = Query(None, description="Filter by keyword in job title"),
    hours: int | None = Query(None, description="Only jobs scraped within the last N hours", ge=1),
    limit: int = Query(100, description="Max number of results", ge=1, le=500),
    offset: int = Query(0, description="Pagination offset", ge=0),
):
    """
    Get job listings with optional filters.

    Query Parameters:
      - `location`: Case-insensitive substring match on job location.
      - `keyword`: Case-insensitive substring match on job title.
      - `hours`: Only return jobs scraped within the last N hours.
      - `limit`: Max results (default 100, max 500).
      - `offset`: Pagination offset.
    """
    jobs = query_jobs(
        location=location,
        keyword=keyword,
        hours=hours,
        limit=limit,
        offset=offset,
    )

    return {
        "count": len(jobs),
        "filters": {
            "location": location,
            "keyword": keyword,
            "hours": hours,
        },
        "jobs": jobs,
    }


@app.post("/scrape", tags=["Admin"])
async def trigger_scrape():
    """Manually trigger a scrape run (runs in background)."""
    import threading

    thread = threading.Thread(target=_run_scrape, daemon=True)
    thread.start()

    return {
        "message": "Scrape triggered in background. Check /status for results.",
        "triggered_at": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/status", tags=["Admin"])
async def scrape_status():
    """Get the status of the last scrape run."""
    return _last_scrape


@app.get("/roles", tags=["Info"])
async def get_roles():
    """Get the configured role tiers being searched."""
    return {
        "role_tiers": ROLE_TIERS,
        "total_queries": sum(len(v) for v in ROLE_TIERS.values()),
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        reload=False,
        log_level="info",
    )
