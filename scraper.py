"""
Job scraper powered by python-jobspy.

Iterates through all role tiers, scrapes each query from configured sites,
normalizes results, and bulk-inserts into SQLite with deduplication.
"""

import logging
import traceback
from datetime import datetime, timezone

from jobspy import scrape_jobs

from config import (
    ALL_ROLES,
    COUNTRY,
    HOURS_OLD,
    IS_REMOTE,
    JOB_RETENTION_DAYS,
    RESULTS_PER_QUERY,
    ROLE_TIERS,
    SCRAPE_SITES,
)
from database import insert_jobs_bulk, purge_old_jobs

logger = logging.getLogger("scraper")


def _normalize_salary(row) -> str:
    """Extract a human-readable salary string from a Jobspy result row."""
    parts: list[str] = []

    min_amt = row.get("min_amount")
    max_amt = row.get("max_amount")
    currency = row.get("currency", "USD")
    interval = row.get("interval", "")

    if min_amt and max_amt:
        parts.append(f"{currency} {min_amt:,.0f}–{max_amt:,.0f}")
    elif min_amt:
        parts.append(f"{currency} {min_amt:,.0f}+")
    elif max_amt:
        parts.append(f"Up to {currency} {max_amt:,.0f}")

    if interval and parts:
        parts.append(f"/{interval}")

    return " ".join(parts) if parts else ""


def _normalize_job(row, site: str, tier_name: str, query: str) -> dict:
    """Convert a Jobspy DataFrame row into our standard job dict."""
    location_parts: list[str] = []
    for field in ("city", "state", "country"):
        val = row.get(field)
        if val and str(val).strip() and str(val).lower() != "nan":
            location_parts.append(str(val).strip())
    location = ", ".join(location_parts) if location_parts else str(row.get("location", "")).strip()

    apply_link = str(row.get("job_url", "") or row.get("job_url_direct", "") or "")

    date_posted = row.get("date_posted", "")
    if hasattr(date_posted, "isoformat"):
        date_posted = date_posted.isoformat()
    elif str(date_posted).lower() == "nan":
        date_posted = ""

    description = str(row.get("description", "") or "")
    if len(description) > 1000:
        description = description[:997] + "..."

    return {
        "job_title": str(row.get("title", "")).strip(),
        "company": str(row.get("company_name", "") or row.get("company", "")).strip(),
        "location": location,
        "salary": _normalize_salary(row),
        "apply_link": apply_link,
        "description": description,
        "date_posted": str(date_posted),
        "source_site": site,
        "role_tier": tier_name,
    }


def scrape_all_roles() -> dict:
    """
    Main scraping entry point. Iterates all role tiers and queries.
    Returns a summary dict with counts.
    """
    started_at = datetime.now(timezone.utc).isoformat()
    total_scraped = 0
    total_inserted = 0
    total_purged = 0
    errors: list[str] = []

    logger.info("=" * 60)
    logger.info(f"🔍 Starting full scrape at {started_at}")
    logger.info(f"   Sites: {SCRAPE_SITES}")
    logger.info(f"   Country: {COUNTRY} | Remote: {IS_REMOTE}")
    logger.info(f"   Hours old: {HOURS_OLD} | Results/query: {RESULTS_PER_QUERY}")
    logger.info("=" * 60)

    for tier_name, roles in ROLE_TIERS.items():
        logger.info(f"\n📋 Tier: {tier_name}")

        for query in roles:
            logger.info(f"   🔎 Searching: '{query}'")

            try:
                df = scrape_jobs(
                    site_name=SCRAPE_SITES,
                    search_term=query,
                    results_wanted=RESULTS_PER_QUERY,
                    hours_old=HOURS_OLD,
                    country_indeed=COUNTRY,
                    is_remote=IS_REMOTE,
                )

                if df is None or df.empty:
                    logger.info(f"      ⚪ No results for '{query}'")
                    continue

                jobs: list[dict] = []
                for _, row in df.iterrows():
                    site = str(row.get("site", "unknown"))
                    normalized = _normalize_job(row, site, tier_name, query)

                    if not normalized["job_title"] or not normalized["company"]:
                        continue

                    jobs.append(normalized)

                total_scraped += len(jobs)

                newly_inserted = insert_jobs_bulk(jobs)
                total_inserted += newly_inserted

                logger.info(
                    f"      ✅ Found {len(jobs)} → Inserted {newly_inserted} new"
                )

            except Exception as e:
                err_msg = f"Error scraping '{query}': {e}"
                logger.error(f"      ❌ {err_msg}")
                logger.debug(traceback.format_exc())
                errors.append(err_msg)

    finished_at = datetime.now(timezone.utc).isoformat()
    total_purged = purge_old_jobs(JOB_RETENTION_DAYS)
    summary = {
        "started_at": started_at,
        "finished_at": finished_at,
        "total_scraped": total_scraped,
        "total_inserted": total_inserted,
        "total_duplicates": total_scraped - total_inserted,
        "total_purged": total_purged,
        "retention_days": JOB_RETENTION_DAYS,
        "errors": errors,
        "error_count": len(errors),
    }

    logger.info("\n" + "=" * 60)
    logger.info(
        f"✅ Scrape complete: {total_scraped} scraped, {total_inserted} new, "
        f"{total_purged} purged, {len(errors)} errors"
    )
    logger.info("=" * 60)

    return summary
