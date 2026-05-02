# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## IMPORTANT Maintenance Rule

ALWAYS UPDATE THIS FILE when there are new features, modified existing features, API changes, database schema changes, frontend flow changes, workflow changes, or meaningful implementation/architecture changes.

A new agent should be able to start from this file and understand the current project structure and behavior without reconstructing recent work from chat history.

## Project Overview

Full-stack local scraping console for automated lead discovery and enrichment.

Backend:
- Flask REST API.
- SQLite persistence.
- Selenium website/email scraping.
- Google Places API lead discovery.

Frontend:
- Vite + React + TypeScript app in `frontend/`.
- TanStack Query for API calls, mutations, polling, and cache refresh.
- Operational UI for scraping, lead management, jobs, exports, dashboard metrics, global data refresh, and collapsible sidebar navigation.

Primary capabilities:
1. Website email scraping: Selenium crawls a single website and returns email addresses directly.
2. Google Maps lead discovery: Google Places Text Search fetches business leads by location/type and stores them in SQLite.
3. Bulk lead email enrichment: background thread scrapes emails for stored leads that have websites and are not already scraped.
4. Lead website context capture: bulk enrichment stores a cleaned public homepage excerpt.
5. Lead management UI: list/filter all leads, inspect details, copy contact data, open websites, edit website/emails/status/context.
6. Job monitoring UI: list/filter jobs, inspect progress, stop running jobs.
7. Dashboard summary: backend summary endpoint powers lead/job metric cards.
8. Campaign workflow: create curated outreach lists from filtered leads, track campaign-specific stages, notes, final email text, contacted state, and export campaign leads.

This is currently a local personal project. There is no authentication. Do not expose the backend publicly without adding auth, request caps, and rate limiting.

## Commands

```bash
# Backend dependencies
pip install -r requirements.txt

# Run backend API at http://localhost:5000
python -m backend.app

# Run all backend tests
pytest

# Run a single backend test file
pytest tests/test_backend_database.py -v

# Run a specific backend test
pytest tests/test_backend_database.py::TestDatabase::test_insert_and_get_job_execution -v

# Run backend tests with coverage
pytest --cov=backend --cov=config
```

Pytest discovery is configured in `pytest.ini` to only collect tests from `tests/` and to ignore runtime/generated folders such as `backend/temp`, `frontend`, `node_modules`, and `venv`.

```bash
# Frontend setup
cd frontend
npm install

# Frontend typecheck
npm run typecheck

# Frontend dev server, usually http://localhost:5173
npm run dev

# Frontend production build
npm run build
```

Required before running backend:
- Create `.env` in project root with `GOOGLE_API_KEY='YOUR_KEY'`.
- Place ChromeDriver/GeckoDriver binaries in `config/drivers/` if local Selenium requires them.

Run backend and frontend in separate terminals:

```bash
# terminal 1, repo root
python -m backend.app

# terminal 2, frontend/
npm run dev
```

The frontend uses Vite proxy routes:
- Browser calls to `/api/*` proxy to `http://localhost:5000/api/*`.
- Browser calls to `/backend-health` proxy to Flask `/`.

## Architecture

### Backend Request Lifecycle

```text
POST /api/scrape/*
  -> Flask Blueprint (backend/routes/api.py)
  -> write_progress() creates or updates job record in SQLite
  -> EmailScraper or Google Places service executes task
  -> Results stored in leads table and/or returned directly
  -> GET /api/progress/<job_id> polls status
  -> POST /api/stop/<job_id> sets stop_call flag in DB
```

### Frontend Request Lifecycle

```text
User action in React page
  -> TanStack Query hook in frontend/src/hooks/*
  -> typed API client in frontend/src/api/*
  -> Vite proxy /api/*
  -> Flask route in backend/routes/api.py
  -> SQLite / Selenium / Google Places service
  -> React renders loading/error/empty/success states
```

## Key Modules

| File | Role |
|------|------|
| `backend/app.py` | Flask app creation, root health route, API blueprint registration, UTF-8 tolerant stdout/stderr setup |
| `backend/routes/api.py` | All REST endpoints for scraping, jobs, leads, summary, export |
| `backend/database.py` | `Database` class, SQLite schema, context manager, thread-safe lock, query methods for jobs, leads, email review, and campaigns |
| `backend/app_settings.py` | `Config` class for paths, env vars, driver locations, log settings |
| `config/job_functions.py` | `write_progress()` upserts job state; `check_stop_signal()` reads DB stop flag |
| `config/logging.py` | `log_function_call` and `log_all_methods` decorators |
| `config/utils.py` | URL validation, email validation, non-business domain filtering |
| `backend/scripts/scraping/scrape_for_email.py` | `EmailScraper` orchestrator: sitemap discovery, page scraping, dedupe |
| `backend/scripts/scraping/page_scraper.py` | Scrapes one page through Selenium and can return emails plus visible body text |
| `backend/scripts/scraping/email_extractor.py` | Extracts emails from page text and `mailto:` links; can also return visible page text |
| `backend/scripts/scraping/sitemap_parser.py` | Discovers URLs via `robots.txt`, XML sitemaps, HTML sitemap fallbacks |
| `backend/scripts/selenium/webdriver_manager.py` | WebDriver factory for Chrome/Firefox, headless mode, Tor proxy |
| `backend/scripts/google_api/google_places.py` | Google Places integration and DB lead storage |
| `pytest.ini` | Pytest collection config; keeps runtime temp folders out of test discovery |
| `frontend/src/App.tsx` | Main React app shell, pages, tables, filters, job/lead panels |
| `frontend/src/api/*` | Typed API clients for health, scraping, jobs, leads, summary |
| `frontend/src/hooks/*` | TanStack Query hooks for server state, mutations, polling, export, updates, and campaign workflows |
| `frontend/vite.config.ts` | Vite React plugin and dev proxy configuration |
| `frontend/src/styles.css` | Application styling and responsive layouts |

## Database Schema

SQLite database path: `backend/temp/scraping.db`.

### `job_executions`

One row per tracked job/step.

Important columns:
- `execution_id`: integer primary key.
- `job_id`: UUID string exposed to API/UI.
- `step_id`: job type, usually `email_scrape`, `google_maps_scrape`, or `leads_email_scrape`.
- `input`: URL, location/type, or lead batch description.
- `max_pages`, `use_tor`, `headless`: scrape options when relevant.
- `status`: `running`, `completed`, `failed`, or `stopped`.
- `current_row`, `total_rows`: progress counters.
- `error_message`: failure details.
- `stop_call`: DB flag checked by long-running jobs.

### `leads`

Business records generated by Google Places and enriched by email scraping.

Important columns:
- `lead_id`: integer primary key.
- `execution_id`: foreign key to `job_executions.execution_id`.
- `place_id`: Google place identifier.
- `location`, `name`, `address`, `phone`, `website`, `emails`.
- `status`: commonly `scraped`, `failed`, `skipped`, `pending`, or null.
- `website_summary`: cleaned visible public website text captured during lead email enrichment.
- `summary_source_url`: page URL used for `website_summary`.
- `summary_status`: `captured`, `empty`, or `failed`.
- `summary_updated_at`: timestamp of the last summary field update.
- `created_at`, `updated_at`.

Uniqueness:
- Leads are unique by `(execution_id, place_id)`.

### `campaigns`

Curated outreach lists created from filtered leads.

Important columns:
- `campaign_id`: integer primary key.
- `name`: campaign name.
- `business_type`, `search_location`: parsed from filters or `lead.location` values such as `dentist:London, UK`.
- `filters_json`: creation filters used to select leads.
- `status`: `draft`, `active`, `paused`, `completed`, or `archived`.
- `notes`, `created_at`, `updated_at`.

### `campaign_leads`

Campaign-specific workflow rows linked to source leads.

Important columns:
- `campaign_lead_id`: integer primary key.
- `campaign_id`, `lead_id`: foreign keys to campaigns and leads.
- `stage`: `review`, `ready_for_email`, `drafted`, `approved`, `contacted`, `replied`, `closed`, `skipped`, or `do_not_contact`.
- `priority`, `email_draft`, `final_email`, `campaign_notes`.
- `contacted_at`, `created_at`, `updated_at`.

Uniqueness:
- Campaign lead membership is unique by `(campaign_id, lead_id)`.

## Job Status Values

Normal lifecycle:

```text
running -> completed | failed | stopped
```

Stop flow:

```text
Client POST /api/stop/<job_id>
  -> backend finds step_id
  -> backend writes stop_call=True and status=stopped
  -> scraper checks check_stop_signal()
  -> background job exits cleanly when it next checks the flag
```

Stop is most useful for the async `leads_email_scrape` flow. Synchronous routes can already be blocking the request that started them.

## Current API Endpoints

All API endpoints are mounted under `/api`, except Flask root health check `/`.

| Method | Path | Purpose | Notes |
|--------|------|---------|-------|
| `GET` | `/` | Backend health check | Frontend calls through `/backend-health` |
| `POST` | `/api/scrape/website-emails` | Synchronously scrape one website for emails | Body: `url`, optional `max_pages`, `use_tor`, `headless`, `sitemap_limit` |
| `POST` | `/api/scrape/google-maps` | Synchronously fetch/store Google Places leads | Body: `location`, optional `radius`, `place_type`, `max_places`; `radius` is currently ignored by Text Search implementation |
| `POST` | `/api/scrape/leads-emails` | Start async email and website context enrichment for stored leads | Returns `202` with `job_id`; poll `/api/progress/<job_id>` |
| `GET` | `/api/progress/<job_id>` | Get job progress/status | Checks known step IDs |
| `POST` | `/api/stop/<job_id>` | Stop a running/stoppable job | Most useful for `leads_email_scrape` |
| `GET` | `/api/leads` | List all leads with filters | Filters: `status`, `job_id`, `has_email=true/false`, `has_website=true/false`, `has_phone=true/false`, `business_type`, `search_location` |
| `GET` | `/api/leads/filter-options` | List distinct scraped campaign filter options | Parses `business_type` and `search_location` dropdown values from existing `leads.location` values |
| `PATCH` | `/api/leads/<lead_id>` | Manually edit lead fields | Editable: `website`, `emails`, `status`; validates website and emails |
| `GET` | `/api/leads/export` | Export contact-ready leads | Default CSV; `?format=json` for JSON; only `status='scraped'` with phone or email |
| `GET` | `/api/campaigns` | List campaigns with stage counts | Campaign list page |
| `POST` | `/api/campaigns` | Create campaign from lead filters | Initial campaign lead stage is `review` |
| `GET` | `/api/campaigns/<campaign_id>` | Get campaign details and stage counts | Campaign detail header |
| `PATCH` | `/api/campaigns/<campaign_id>` | Edit campaign metadata | Editable: `name`, `status`, `notes` |
| `GET` | `/api/campaigns/<campaign_id>/leads` | List campaign leads joined to lead data | Filters: `stage`, `lead_flag`, `lead_status`, `has_email`, `has_website`, `search` |
| `PATCH` | `/api/campaign-leads/<campaign_lead_id>` | Update campaign lead workflow fields | Editable: `stage`, `priority`, `email_draft`, `final_email`, `campaign_notes`, `contacted_at` |
| `GET` | `/api/campaigns/<campaign_id>/export` | Export campaign leads | Default CSV; `?format=json`; optional `stage` filter |
| `GET` | `/api/jobs` | List job history with filters | Filters: `status`, `step_id`, `limit`; limit capped at 200 |
| `GET` | `/api/summary` | Dashboard summary counts | Counts lead pipeline and job statuses |

## Endpoint Details

### `POST /api/scrape/website-emails`

Request:

```json
{
  "url": "https://example.com",
  "max_pages": 10,
  "use_tor": false,
  "headless": true,
  "sitemap_limit": 10
}
```

Response:

```json
{
  "job_id": "uuid",
  "input": "https://example.com",
  "emails": ["hello@example.com"],
  "status": "completed"
}
```

Business logic:
- Validates URL with `validate_url()`.
- Creates `email_scrape` job.
- Uses Selenium to inspect robots/sitemaps and scrape likely contact/about pages.
- Returns emails directly.

### `POST /api/scrape/google-maps`

Request:

```json
{
  "location": "Sarande, Albania",
  "radius": 300,
  "place_type": "lodging",
  "max_places": 20
}
```

Response:

```json
{
  "job_id": "uuid",
  "input": "lodging:Sarande, Albania",
  "status": "completed",
  "leads": []
}
```

Business logic:
- Uses Google Places Text Search endpoint.
- Stores leads in SQLite.
- Normalizes websites with `extract_base_url()`.
- Current route is synchronous.

### `POST /api/scrape/leads-emails`

Request:

```json
{
  "max_pages": 30,
  "use_tor": false,
  "headless": true
}
```

Started response:

```json
{
  "job_id": "uuid",
  "status": "started",
  "total_leads": 10
}
```

No-work response:

```json
{
  "message": "No unscraped leads found.",
  "count": 0
}
```

Business logic:
- Reads leads with websites where status is not `scraped`.
- Starts background thread.
- Validates each website.
- Scrapes emails and updates lead `emails` and `status`.
- Captures cleaned visible public homepage text into `website_summary` when useful homepage text is found.
- Summary capture is intentionally simple: it uses the lead website homepage only and does not try about/service/contact fallback pages.
- One-off `/api/scrape/website-emails` remains email-only and does not capture/store website summary context.
- Summary status is stored as `captured`, `empty`, or `failed`; no LLM/API summarization is used.

### `GET /api/leads`

Filters:
- `status`
- `job_id`
- `has_email=true|false`
- `has_website=true|false`
- `has_phone=true|false`
- `lead_flag`
- `lead_status`
- `business_type`
- `search_location`

Response:

```json
{
  "count": 1,
  "leads": [
    {
      "lead_id": 1,
      "execution_id": 1,
      "place_id": "abc",
      "location": "lodging:Sarande, Albania",
      "name": "Business",
      "address": "Address",
      "phone": "+123",
      "website": "https://example.com",
      "emails": "hello@example.com",
      "status": "scraped",
      "website_summary": "Cleaned public website context...",
      "summary_source_url": "https://example.com/about",
      "summary_status": "captured",
      "summary_updated_at": "timestamp",
      "campaign_count": 1,
      "campaign_names": ["Dentists London May 2026"],
      "campaign_memberships": [
        {
          "campaign_id": 1,
          "campaign_name": "Dentists London May 2026",
          "stage": "review"
        }
      ],
      "created_at": "timestamp",
      "updated_at": "timestamp",
      "job_id": "uuid",
      "step_id": "google_maps_scrape",
      "job_status": "completed"
    }
  ]
}
```

### `PATCH /api/leads/<lead_id>`

Request:

```json
{
  "website": "https://example.com",
  "emails": "hello@example.com",
  "status": "scraped"
}
```

Response:

```json
{
  "lead": {}
}
```

Notes:
- `website` is validated and normalized when non-empty.
- `emails` can be a comma-separated string or a list.
- Emails are validated and example/test domains are filtered.
- `website_summary` is editable so captured context can be manually cleaned up from the lead detail panel.

### `GET /api/jobs`

Filters:
- `status`
- `step_id`
- `limit`

Response:

```json
{
  "count": 1,
  "jobs": [
    {
      "execution_id": 1,
      "job_id": "uuid",
      "step_id": "google_maps_scrape",
      "input": "lodging:Sarande, Albania",
      "status": "completed",
      "current_row": 20,
      "total_rows": 20,
      "created_at": "timestamp",
      "updated_at": "timestamp",
      "error_message": null,
      "stop_call": 0
    }
  ]
}
```

### `GET /api/summary`

Response:

```json
{
  "leads": {
    "total": 0,
    "with_website": 0,
    "with_email": 0,
    "pending_enrichment": 0,
    "scraped": 0,
    "failed": 0,
    "skipped": 0
  },
  "jobs": {
    "total": 0,
    "running": 0,
    "completed": 0,
    "failed": 0,
    "stopped": 0
  }
}
```

## Frontend Structure

The frontend is currently a single React app with internal page state, not React Router.

Pages in `frontend/src/App.tsx`:

| Page | Purpose | APIs |
|------|---------|------|
| Dashboard | Backend health, summary cards, recent jobs | `/`, `/api/summary`, `/api/jobs` |
| Find Businesses | Search Google Places and store leads | `/api/scrape/google-maps` |
| Website Emails | One-off website email scrape | `/api/scrape/website-emails` |
| Enrich Leads | Start bulk email enrichment and poll progress | `/api/scrape/leads-emails`, `/api/progress/<job_id>`, `/api/stop/<job_id>` |
| Leads | List/filter leads, row actions, detail panel, manual edits, CSV export | `/api/leads`, `/api/leads/<lead_id>`, `/api/leads/export` |
| Campaigns | Create campaigns from lead filters, review campaign leads, update stages/priority/notes/final email, export campaign CSV | `/api/campaigns`, `/api/campaigns/<campaign_id>`, `/api/campaigns/<campaign_id>/leads`, `/api/campaign-leads/<campaign_lead_id>`, `/api/campaigns/<campaign_id>/export` |
| Jobs | List/filter job history, select job details, stop running jobs | `/api/jobs`, `/api/progress/<job_id>`, `/api/stop/<job_id>` |
| Settings | Static runtime info for local frontend/backend defaults | none |

Frontend API clients:
- `frontend/src/api/httpClient.ts`: fetch wrapper, base URLs, `ApiError`, download helper.
- `frontend/src/api/healthApi.ts`: backend health.
- `frontend/src/api/scrapingApi.ts`: scrape mutations.
- `frontend/src/api/jobsApi.ts`: job list, progress, stop.
- `frontend/src/api/leadsApi.ts`: lead list, patch, export.
- `frontend/src/api/summaryApi.ts`: dashboard summary.
- `frontend/src/api/types.ts`: shared TypeScript response/request types.

Frontend hooks:
- `useBackendHealth()`
- `useWebsiteEmailScrape()`
- `useGoogleMapsScrape()`
- `useLeadEmailEnrichment()`
- `useJobPolling(jobId)`
- `useJobs(params)`
- `useStopJob()`
- `useLeads(params)`
- `useUpdateLead()`
- `useExportLeadsJson()`
- `useSummary()`

## Current UI Behavior

### Leads Page

Supports:
- Filtering by status, job ID, has email, has website.
- Filtering by scrape status, job ID, has email, has website, has phone, lead flag, and lead review status from the filter panel.
- The leads table header also has client-side UI filters: Name search in the Name column, Business type and Location dropdowns in the Location column, and Campaign dropdown in the Campaign column. These header filters operate on the currently loaded lead list rather than adding backend query parameters.
- Client-side pagination with page sizes 10, 30, 50, 100, and All.
- Quick `Needs enrichment` filter.
- Row click expands/collapses lead details directly below the selected row; there is no persistent empty side panel.
- Lead table rows are lightly color-coded by scrape status: scraped rows green, failed rows red, and skipped rows yellow.
- Open website.
- Copy emails.
- Copy phone.
- Copy formatted lead text.
- The row action controls are always rendered for stable alignment: external-link icon for website, mail icon for email copy, phone icon for phone copy, copy icon for formatted lead copy. Website/email/phone actions are disabled when the row lacks the required value.
- Edit website, emails, status, notes, and website context through `PATCH /api/leads/<lead_id>`.
- Lead flag and lead review status are edited directly from their colored badges in the lead table row or expanded header.
- CSV export through `/api/leads/export`.
- Table layout keeps Status/Actions visible by wrapping website URLs and email tokens while keeping phone numbers on one line. The Actions column stays a normal table cell so row heights match wrapped content; its buttons sit in an inner flex row.

### Jobs Page

Supports:
- Filtering by status, step ID, and limit.
- Row click expands/collapses job progress details directly below the selected row; there is no persistent empty side panel.
- Progress details from `/api/progress/<job_id>`.
- Stop action for running jobs.

### Dashboard

Shows:
- Backend health.
- Workflow outline.
- Lead/job summary cards from `/api/summary`.
- Recent jobs from `/api/jobs`.

### Global Refresh

The top bar includes a Refresh button on every tab. It calls TanStack Query `invalidateQueries()` so active backend-backed UI data refetches without a full page reload.

### Sidebar Layout

The left navigation sidebar can collapse/expand through the small top-left icon. Collapsed mode keeps icon-only navigation visible and gives more horizontal space to data tables.

## Logging

- `@log_function_call` wraps functions and logs entry, return values, Flask responses, and exceptions.
- `@log_all_methods` wraps every method on decorated classes, currently used on `Database`.
- Log files rotate at 100 MB and are stored in `backend/log_files/`.
- `backend/app.py` reconfigures stdout/stderr as UTF-8 with replacement to avoid Windows console logging failures for Google Places names containing special Unicode.
- Selenium WebDriver page-load and script timeouts are set to 12 seconds to keep dead or slow pages from blocking lead enrichment for too long.

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `GOOGLE_API_KEY` | none | Required for Google Places scraping |
| `LOG_LEVEL` | `INFO` | App log level |
| `MAX_THREADS` | `5` | Max concurrent email scraping threads |
| `TOR_EXECUTABLE` | OS-specific path | Path to Tor binary |
| `LIBRARY_LOG_LEVELS` | JSON map | Per-library log suppression |

## Known Tech Debt and Limitations

- `update_job_status()` in `config/job_functions.py` still writes JSON tracking files alongside the DB. This is legacy tracking and marked for deprecation. New code should use the `Database` class.
- No authentication is implemented. This is fine for local personal use, but do not expose publicly without auth, request caps, and rate limiting.
- `/api/scrape/google-maps` is synchronous in code, despite some older README/Postman wording saying async.
- `radius` is accepted by `/api/scrape/google-maps` but ignored by the current Google Places Text Search implementation.
- Frontend is concentrated in `frontend/src/App.tsx`. If the UI grows further, split pages/components into separate files.
- Clipboard features use `navigator.clipboard`, which works on localhost/secure contexts.
- Manual lead editing supports website, legacy emails string, scrape status, lead flag, lead review status, notes, and captured website context.

## Lead and Email Review System

The app now has a lightweight review layer on top of raw scraped leads.

Lead review fields added to `leads`:
- `lead_flag`: `needs_review`, `good`, `bad`, `hot`.
- `lead_status`: `new`, `reviewed`, `ready`, `contacted`, `do_not_contact`.
- `notes`: manual review notes.

Normalized email review table:
- `lead_emails.email_id`
- `lead_emails.lead_id`
- `lead_emails.email`
- `lead_emails.category`: `unknown`, `booking`, `info`, `sales`, `support`, `accounting`, `manager`.
- `lead_emails.status`: `new`, `valid`, `invalid`, `do_not_use`.
- `lead_emails.is_primary`
- `lead_emails.notes`

Existing comma-separated `leads.emails` data is backfilled into `lead_emails` during DB initialization. The old `leads.emails` field remains for compatibility and CSV export. When normalized email rows are added, updated, or deleted, `leads.emails` is synced from usable rows, excluding `invalid` and `do_not_use`.

Additional endpoints:
- `GET /api/leads/<lead_id>/emails`
- `POST /api/leads/<lead_id>/emails`
- `PATCH /api/lead-emails/<email_id>`
- `DELETE /api/lead-emails/<email_id>`

`GET /api/leads` also supports `lead_flag` and `lead_status` filters.

Lead detail UI now supports:
- Editing lead flag, review status, notes, and captured website context.
- Reviewing individual emails.
- Setting email category/status.
- Marking one primary email.
- Adding manual emails.
- Deleting bad emails.
- Email review rows are vertically stacked in the narrow lead detail panel so long email addresses remain readable; controls appear below the email text.
- Captured website context is shown in the lead detail panel with summary status, source URL, and last summary update timestamp.

## Campaign Workflow

Campaigns are a workflow layer over existing leads. Lead records remain the source of truth for business/contact data, and campaign stages do not overwrite base lead status.

Current behavior:
- Campaigns are created from filters matching `/api/leads`, including scrape status, email/website/phone presence, lead flag, lead review status, business type, and search location.
- Campaign creation uses live dropdowns for business type and search location from `/api/leads/filter-options`, parsed from existing scraped `leads.location` values like `dentist:London, UK`. The endpoint returns distinct business type counts, distinct location counts, and business type/location pair counts. The frontend uses those pair counts to make the two dropdowns dependent: selecting a business type narrows locations to only locations scraped for that type, selecting a location narrows business types to only types scraped there, and option labels show counts.
- Campaign creation stores the filters JSON and links matching leads in `campaign_leads` with initial stage `review`.
- Leads can belong to multiple campaigns; `/api/leads` includes `campaign_count`, `campaign_names`, and detailed `campaign_memberships`.
- The Leads tab shows a Campaign column and expanded lead details list campaign memberships.
- The Campaigns tab lists campaigns, creates campaigns, opens campaign detail, filters campaign leads by stage/search, updates stage and priority inline, edits campaign notes/email draft/final email, marks leads contacted, and exports campaign CSV.
- Campaign detail stage counts are interactive buttons. Selecting a stage button filters the campaign lead table to that exact stage; selecting `All` shows every campaign lead. When a lead is moved from one stage to another, it should disappear from the previous active stage view after the campaign lead query refreshes.
