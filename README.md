# 🔍 Job Listings MCP Server

A standalone Python microservice that **scrapes fresh job listings** using [Jobspy](https://github.com/Bunsly/JobSpy), stores them in SQLite with deduplication, and exposes a **`/jobs` REST endpoint** for embedding in a portfolio site as a live feed.

---

## ⚡ Features

- **Multi-site scraping** — LinkedIn, Indeed (Glassdoor + ZipRecruiter optional)
- **Tiered role search** — 4 priority tiers of job roles (Solutions Engineer → Data Analyst)
- **Smart deduplication** — Unique constraint on `(job_title, company, location)`
- **APScheduler** — Automated scrapes every 1 hour (configurable)
- **Query filtering** — `?location=`, `?keyword=`, `?hours=` query params
- **CORS-enabled** — Ready for cross-origin fetch from your portfolio
- **Deploy-ready** — Dockerfile, Procfile, and railway.toml included

---

## 🏗️ Architecture

```
APScheduler (1hr)  →  Jobspy Scraper  →  SQLite (deduped)  ←  FastAPI /jobs
                                                                    ↕
                                                          Portfolio Site (fetch)
```

---

## 📋 Role Tiers

| Tier | Roles |
|------|-------|
| **T1 — Primary** | Solutions Engineer, Pre-sales Engineer, Forward Deployed Engineer |
| **T2 — Secondary** | AI Solutions Engineer, AI Implementation Consultant, AI Product Specialist |
| **T3 — Tertiary** | Implementation Consultant, Technical Consultant, SaaS Implementation Analyst |
| **T4 — Fallback** | Business Analyst, Data Analyst |

---

## 🚀 Quick Start

### 1. Clone & Install

```bash
cd jobs-mcp-server
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env as needed
```

### 3. Run

```bash
python main.py
```

The server starts at `http://localhost:8000`. An initial scrape runs automatically in the background.

---

## 📡 API Endpoints

### `GET /` — Health Check

```json
{
  "status": "healthy",
  "service": "Job Listings MCP Server",
  "total_jobs_in_db": 142,
  "scrape_interval_hours": 1
}
```

### `GET /jobs` — List Job Listings

**Query Params:**

| Param      | Type   | Description                                  |
|------------|--------|----------------------------------------------|
| `location` | string | Filter by location (substring, case-insensitive) |
| `keyword`  | string | Filter by keyword in job title               |
| `hours`    | int    | Only jobs scraped within the last N hours     |
| `limit`    | int    | Max results (default 100, max 500)           |
| `offset`   | int    | Pagination offset                            |

**Example:**

```bash
curl "http://localhost:8000/jobs?location=San%20Francisco&keyword=AI&hours=24"
```

**Response:**

```json
{
  "count": 5,
  "filters": {
    "location": "San Francisco",
    "keyword": "AI",
    "hours": 24
  },
  "jobs": [
    {
      "id": 1,
      "job_title": "AI Solutions Engineer",
      "company": "Acme Corp",
      "location": "San Francisco, CA",
      "salary": "USD 120,000–160,000/yearly",
      "apply_link": "https://linkedin.com/jobs/...",
      "date_posted": "2025-01-15",
      "date_scraped": "2025-01-15T12:00:00+00:00",
      "source_site": "linkedin",
      "role_tier": "T2 — Secondary"
    }
  ]
}
```

### `POST /scrape` — Manual Trigger

Triggers a scrape run in the background.

```bash
curl -X POST http://localhost:8000/scrape
```

### `GET /status` — Last Scrape Status

```bash
curl http://localhost:8000/status
```

### `GET /roles` — Configured Role Tiers

```bash
curl http://localhost:8000/roles
```

---

## 🐳 Deployment

### Railway

1. Push the `jobs-mcp-server/` directory to a new GitHub repo (or subdirectory).
2. Connect Railway to the repo.
3. Railway auto-detects the Dockerfile.
4. Add a **Volume** at `/data` to persist the SQLite DB.
5. Set environment variables in the Railway dashboard.

### Render

1. Create a new **Web Service**.
2. Point to the repo/directory.
3. Set **Build Command:** `pip install -r requirements.txt`
4. Set **Start Command:** `python main.py`
5. Add a **Disk** at `/data` and set `DATA_DIR=/data`.

---

## 🔗 Portfolio Integration

In your Next.js portfolio, fetch from the deployed URL:

```tsx
// In a Next.js API route or client component
const API_URL = process.env.NEXT_PUBLIC_JOBS_API_URL || 'https://your-jobs-server.up.railway.app';

async function fetchJobs(filters?: { location?: string; keyword?: string; hours?: number }) {
  const params = new URLSearchParams();
  if (filters?.location) params.set('location', filters.location);
  if (filters?.keyword) params.set('keyword', filters.keyword);
  if (filters?.hours) params.set('hours', String(filters.hours));

  const res = await fetch(`${API_URL}/jobs?${params.toString()}`);
  return res.json();
}
```

---

## 📝 Environment Variables

| Variable               | Default                          | Description                        |
|------------------------|----------------------------------|------------------------------------|
| `SCRAPE_INTERVAL_HOURS`| `1`                              | Hours between automated scrapes    |
| `RESULTS_PER_QUERY`    | `25`                             | Max results per search query       |
| `HOURS_OLD`            | `24`                             | Only scrape jobs posted within N hours |
| `COUNTRY`              | `USA`                            | Country filter for Indeed           |
| `IS_REMOTE`            | `false`                          | Filter for remote-only jobs        |
| `SCRAPE_SITES`         | `linkedin,indeed`                | Comma-separated sites to scrape    |
| `ALLOWED_ORIGINS`      | `http://localhost:3000,...`       | CORS allowed origins               |
| `HOST`                 | `0.0.0.0`                        | Server host                        |
| `PORT`                 | `8000`                           | Server port                        |
| `DATA_DIR`             | `.`                              | Directory for SQLite DB file       |

---

## 📁 Project Structure

```
jobs-mcp-server/
├── main.py              # FastAPI app + APScheduler + endpoints
├── scraper.py           # Jobspy scraping logic
├── database.py          # SQLite schema + CRUD
├── config.py            # Configuration + role tiers
├── requirements.txt     # Python dependencies
├── Dockerfile           # Container build
├── Procfile             # Render process file
├── railway.toml         # Railway config
├── .env.example         # Environment template
├── .gitignore           # Git ignore rules
└── README.md            # This file
```

---

## License

MIT
