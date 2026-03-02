"""
Configuration for the Job Listings MCP Server.
All tunables live here — role tiers, scrape intervals, search parameters.
"""

import os
from pathlib import Path

DATA_DIR = Path(os.getenv("DATA_DIR", "."))
DB_PATH = DATA_DIR / "jobs.db"

SCRAPE_INTERVAL_HOURS = int(os.getenv("SCRAPE_INTERVAL_HOURS", "1"))

RESULTS_PER_QUERY = int(os.getenv("RESULTS_PER_QUERY", "25"))
HOURS_OLD = int(os.getenv("HOURS_OLD", "24"))  # only jobs posted in last N hours
COUNTRY = os.getenv("COUNTRY", "INDIA")
IS_REMOTE = os.getenv("IS_REMOTE", "").lower() in ("true", "1", "yes")

SCRAPE_SITES: list[str] = os.getenv("SCRAPE_SITES", "linkedin,indeed,glassdoor").split(",")

ROLE_TIERS: dict[str, list[str]] = {
    "T1 — Primary": [
        "Solutions Engineer",
        "Pre-sales Engineer",
        "Forward Deployed Engineer",
    ],
    "T2 — Secondary": [
        "AI Solutions Engineer",
        "AI Implementation Consultant",
        "AI Product Specialist",
    ],
    "T3 — Tertiary": [
        "Implementation Consultant",
        "Technical Consultant",
        "SaaS Implementation Analyst",
    ],
    "T4 — Fallback": [
        "Business Analyst",
        "Data Analyst",
        "GenAI Analyst"
    ],
}

ALL_ROLES: list[str] = [
    role for roles in ROLE_TIERS.values() for role in roles
]

ALLOWED_ORIGINS: list[str] = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,https://yashvardhan.dev,https://www.yashvardhan.dev",
).split(",")

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
