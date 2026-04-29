# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project Overview

Flask REST API backend for automated web scraping. Two primary capabilities:
1. **Email scraping** — Selenium-driven browser crawls websites to extract email addresses (synchronous, returns results directly)
2. **Google Maps scraping** — Google Places API fetches business leads by location/type, runs as background threads

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application (http://localhost:5000)
python -m backend.app

# Run all tests
pytest

# Run a single test file
pytest tests/test_backend_database.py -v

# Run a specific test
pytest tests/test_backend_database.py::TestDatabase::test_insert_and_get_job_execution -v

# Run with coverage
pytest --cov=backend --cov=config
```

**Required before running:** Create `.env` in project root with `GOOGLE_API_KEY='YOUR_KEY'`. Place ChromeDriver/GeckoDriver binaries in `config/drivers/`.

## Architecture

### Request Lifecycle

```
POST /api/scrape/*
  → Flask Blueprint (backend/routes/api.py)
  → write_progress() creates job record in SQLite
  → EmailScraper OR GooglePlacesAPI executes task
  → Results stored in leads table / returned directly
  → GET /api/progress/<job_id> polls status
  → POST /api/stop/<job_id> sets stop_call flag in DB
```

### Key Modules

| File | Role |
|------|------|
| `backend/routes/api.py` | All 5 API endpoints; Google Maps jobs spawned as `threading.Thread` |
| `backend/database.py` | `Database` class — context manager, thread-safe via `threading.RLock()`, all queries parameterized |
| `backend/app_settings.py` | `Config` class — single source of truth for paths, env vars, driver locations, log settings |
| `config/job_functions.py` | `write_progress()` upserts job state; `check_stop_signal()` reads stop flag from DB |
| `config/logging.py` | `log_function_call` (function decorator) and `log_all_methods` (class decorator) for automatic tracing |
| `config/utils.py` | URL validation, email validation, non-business domain filtering |
| `backend/scripts/scraping/scrape_for_email.py` | `EmailScraper` orchestrator — sitemap parsing → page scraping → deduplication |
| `backend/scripts/scraping/sitemap_parser.py` | Discovers URLs via `robots.txt` and `sitemap.xml` |
| `backend/scripts/selenium/webdriver_manager.py` | `WebDriverManager` factory — Chrome/Firefox, headless mode, optional Tor proxy |
| `backend/scripts/google_api/google_places.py` | Google Places API wrapper; geocodes location strings, stores leads in DB |

### Database Schema (SQLite at `backend/temp/scraping.db`)

- **`job_executions`** — one row per job: `job_id` (UUID), `step_id`, `input`, `status`, `current_row`, `total_rows`, `stop_call`, `error_message`
- **`leads`** — business records linked to jobs: `place_id` (dedup key), `name`, `address`, `phone`, `website`, `emails`

### Job Status Values

`running` → `completed` | `failed` | `stopped`

Stop flow: client POSTs `/api/stop/<job_id>` → sets `stop_call=True` in DB → scraper polls `check_stop_signal()` each iteration → exits cleanly.

### Logging Decorators

- `@log_function_call` — wraps any function; logs entry args at DEBUG, return value at DEBUG, Flask responses at INFO, exceptions at ERROR
- `@log_all_methods` — class-level decorator that applies `log_function_call` to every method (used on `Database` class)

Log files rotate at 100 MB, stored in `backend/log_files/` with date-based filenames.

### Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `GOOGLE_API_KEY` | — | Required for Google Maps scraping |
| `LOG_LEVEL` | `INFO` | App log level |
| `MAX_THREADS` | `5` | Thread pool size for concurrent jobs |
| `TOR_EXECUTABLE` | OS-specific path | Path to Tor binary |
| `LIBRARY_LOG_LEVELS` | JSON map | Per-library log suppression |

### Known Tech Debt

`update_job_status()` in `config/job_functions.py` writes JSON tracking files alongside the DB — this is the old job-tracking system and is marked for deprecation. New code should only use the `Database` class.
