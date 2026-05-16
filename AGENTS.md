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
- React Router for first-class page URLs and refresh-safe navigation.
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
9. AI-assisted campaign email drafting: generate provider-backed outreach drafts from campaign lead context for manual review and approval.
10. Email category rule management: automatically categorize generic scraped emails by exact local-part rules and review unknown patterns.
11. Gmail draft creation: connect a local Gmail account with OAuth and create one reviewed campaign email draft at a time from `campaign_leads.final_email`.

This is currently a local personal project. There is no authentication. Do not expose the backend publicly without adding auth, request caps, and rate limiting.

## Commands

IMPORTANT user-run command rule:
- Do not run project commands yourself in this repository unless the user explicitly asks you to execute them.
- When verification, setup, tests, builds, dev servers, or other terminal commands are needed, provide the exact commands for the user to run.
- The user should run those commands manually and share the output if they want help interpreting or fixing failures.

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

Pytest discovery is configured in `pytest.ini` to put the repo root on `PYTHONPATH`, only collect tests from `tests/`, and ignore runtime/generated folders such as `backend/temp`, `frontend`, `node_modules`, and `venv`.

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
- For Gmail draft creation, enable the Gmail API in Google Cloud, create an OAuth client, and place the downloaded OAuth client JSON at `config/gmail_client_secret.json`. Gmail user tokens are stored locally at `backend/temp/gmail_token.json`.
- For the default Gmail OAuth flow, register this exact authorized redirect URI in the Google Cloud OAuth client: `http://localhost:5000/api/gmail/auth/callback`. If the backend port changes, register the matching callback URL.
- If the Google OAuth consent screen is in Testing mode, add the Gmail account as a test user before connecting from Settings.
- Do not commit `config/gmail_client_secret.json`, `backend/temp/gmail_token.json`, or any OAuth token/client secret files.

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

Frontend route URLs are handled client-side by React Router. Refresh-safe pages include `/dashboard`, `/discover`, `/website-emails`, `/enrich`, `/leads`, `/campaigns`, `/email-rules`, `/jobs`, and `/settings`.

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
| `backend/database.py` | `Database` class, explicit SQLite initialization/migrations, context manager, thread-safe lock, query methods for jobs, leads, email review, and campaigns |
| `backend/app_settings.py` | `Config` class for paths, env vars, driver locations, log settings |
| `backend/ai_email_service.py` | Provider-neutral AI email draft generation wrapper for OpenAI and Anthropic |
| `backend/gmail_service.py` | Local Gmail OAuth and Gmail API draft creation service using `gmail.compose` scope |
| `config/job_functions.py` | `write_progress()` upserts job state; `check_stop_signal()` reads DB stop flag |
| `config/logging.py` | `log_function_call` and `log_all_methods` decorators |
| `config/utils.py` | URL validation, email validation, exact/subdomain non-business domain filtering |
| `backend/scripts/scraping/scrape_for_email.py` | `EmailScraper` orchestrator: sitemap discovery, bounded worker WebDriver pool page scraping, dedupe |
| `backend/scripts/scraping/page_scraper.py` | Scrapes one page through Selenium and can return emails plus visible body text |
| `backend/scripts/scraping/email_extractor.py` | Extracts emails from page text and `mailto:` links; can also return visible page text plus cleaned HTML context |
| `backend/scripts/scraping/html_context_cleaner.py` | Cleans page HTML into readable website context by removing scripts, nav/header/footer, cookie/privacy/popup blocks, then preserving headings/lists/body text |
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

Initialization behavior:
- `Database()` construction is intentionally cheap. It only resolves the database path and instance fields.
- Schema creation, seed data, and data migrations run through `Database().initialize()`.
- `backend/app.py` calls `Database().initialize()` once at Flask startup after `Config.init_dirs()`.
- Tests that create temporary databases must call `Database(db_path=...).initialize()` before opening the DB with the context manager.
- Migrations use SQLite `PRAGMA user_version`. Version `1` creates the current schema, seeds default settings/category rules, migrates global lead uniqueness/discovery history, and backfills legacy comma-separated `leads.emails` values into `lead_emails`.
- Already-versioned local databases also run cheap additive compatibility migrations on startup, currently used to add Gmail draft metadata columns to existing `campaign_leads` tables without bumping `PRAGMA user_version`.
- Request/progress hot paths such as `write_progress()`, `check_stop_signal()`, route handlers, and polling endpoints should construct `Database()` without rerunning schema setup or global backfills.

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

Canonical business records generated by Google Places and enriched by email scraping. Google Places leads are globally deduplicated by `place_id`; repeated discoveries update the same lead instead of creating another lead row.

Important columns:
- `lead_id`: integer primary key.
- `execution_id`: foreign key to the first/canonical `job_executions.execution_id` that created the lead. It is kept for backward-compatible joins and API fields.
- `place_id`: Google place identifier.
- `location`, `name`, `address`, `phone`, `website`, `emails`.
- `status`: commonly `scraped`, `failed`, `skipped`, `pending`, or null.
- `website_summary`: cleaned visible public website text captured during lead email enrichment.
- `summary_source_url`: page URL used for `website_summary`.
- `summary_status`: `captured`, `empty`, or `failed`.
- `summary_updated_at`: timestamp of the last summary field update.
- `created_at`, `updated_at`.

Uniqueness:
- Leads are globally unique by `place_id`.

Migration behavior:
- Existing duplicate lead rows with the same `place_id` are merged during versioned database initialization.
- Campaign memberships, normalized emails, notes, review fields, scrape status, and website context are preserved on the canonical lead when possible.
- Google Places rediscovery only refreshes source-owned fields such as `location`, `name`, `address`, `phone`, and `website`; it does not overwrite emails, review fields, notes, campaigns, or website summaries.

### `lead_discoveries`

Discovery history for canonical leads.

Important columns:
- `discovery_id`: integer primary key.
- `lead_id`: canonical lead foreign key.
- `execution_id`: scrape job that discovered or rediscovered the lead.
- `place_id`: Google place identifier copied for lookup/debugging.
- `location`: stored search string such as `dentist:London, UK`.
- `business_type`, `search_location`: parsed filter values from `location`.
- `created_at`, `updated_at`.

Uniqueness:
- A lead can have at most one discovery row per execution: `(lead_id, execution_id)`.

Implementation behavior:
- `/api/leads` still returns canonical `execution_id`, `job_id`, `step_id`, and `job_status` from the first/canonical discovery job.
- `job_id`, `business_type`, and `search_location` filters use `lead_discoveries`, so rediscovered canonical leads still appear when filtering by a newer scrape job or search.
- Lead list responses may include additive discovery metadata: `discovery_count`, `last_discovered_at`, and `last_discovery_job_id`.

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
- `gmail_draft_id`, `gmail_message_id`, `gmail_draft_status`, `gmail_drafted_at`, `gmail_error`: Gmail draft creation metadata for reviewed final emails.

Uniqueness:
- Campaign lead membership is unique by `(campaign_id, lead_id)`.

Implementation behavior:
- Campaign `stage` is campaign-specific, but setting a campaign lead stage to `contacted` also updates the linked base `leads.lead_status` to `contacted` so the Leads tab reflects completed outreach.
- Startup compatibility migrations backfill this same status for existing `campaign_leads.stage='contacted'` rows, except base leads already marked `do_not_contact`.

### `app_settings`

Simple key/value settings table for local application configuration.

Current AI email keys:
- `ai_email_provider`: `openai` or `anthropic`.
- `ai_email_model`: provider model name.
- `ai_email_system_prompt`: system prompt used for campaign email drafting.
- `ai_email_user_prompt`: user prompt/template used as part of the structured generation request.

Current operational settings keys:
- `app_log_level`: persisted logging verbosity, one of `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`.
- `scraper_max_pages`, `scraper_sitemap_limit`, `scraper_headless`, `scraper_use_tor`, `scraper_max_threads`: defaults for website/email scraping forms and runtime scraper concurrency.
- `places_place_type`, `places_max_places`, `places_radius`: defaults for Google Places discovery forms. `places_radius` is retained for compatibility, but the current Text Search flow ignores radius.

API keys are not stored in SQLite and are never returned to the frontend. They are read from environment variables.
Gmail OAuth secrets/tokens are not stored in SQLite. The OAuth client file lives at `config/gmail_client_secret.json`; the user token lives at `backend/temp/gmail_token.json`.

### `business_type_email_rules`

Per-business-type personalization rules used by AI campaign email drafting.

Important columns:
- `business_type`: primary key matching parsed lead/campaign business types such as `dentist`.
- `business_description`: specific description to use for that type.
- `pain_point`: specific problem for that type.
- `offer_angle`: automation/service angle to emphasize.
- `extra_instructions`: optional extra prompt guidance.

### `email_category_rules`

Exact local-part rules used to categorize normalized `lead_emails` rows.

Important columns:
- `pattern`: lowercased email local-part such as `info`, `finance`, `reservation`, or `events`.
- `match_type`: currently only `local_part_exact`.
- `category`: non-unknown email category.
- `is_active`: active/inactive rule flag.

Default seeded rules include common generic local-parts for `info`, `sales`, `support`, `accounting`, `finance`, `events`, `booking`, `manager`, `reception`, `hr`, and `marketing`.

Implementation behavior:
- A SQLite trigger classifies newly inserted `lead_emails` rows when their category is empty or `unknown`.
- Existing unknown rows are only updated when `/api/email-category-rules/apply` is called.
- Manual/non-unknown categories are not overwritten by automatic rule application.

## Job Status Values

Normal lifecycle:

```text
running -> completed | failed | stopped
```

Stop flow:

```text
Client POST /api/stop/<job_id>
  -> backend finds step_id
  -> backend writes stop_call=True while keeping status=running
  -> scraper checks check_stop_signal()
  -> background job writes status=stopped when it observes the flag and exits
```

`POST /api/stop/<job_id>` can return `status="stopping"` while the background thread is still exiting. The frontend keeps polling because `/api/progress/<job_id>` remains `running` until the worker finishes. Stop is most useful for the async `leads_email_scrape` flow. Synchronous routes can already be blocking the request that started them.

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
| `POST` | `/api/campaign-leads/<campaign_lead_id>/generate-email` | Generate one AI email draft for a campaign lead | Stores result in `email_draft`; does not overwrite `final_email` |
| `POST` | `/api/campaigns/<campaign_id>/generate-emails` | Batch-generate AI drafts for eligible campaign leads | Body supports optional `stage`, `search`, `limit`; no automatic sending; skips approved/contacted/final workflow stages |
| `GET` | `/api/campaigns/<campaign_id>/export` | Export campaign leads | Default CSV; `?format=json`; optional `stage` filter |
| `GET` | `/api/email-settings` | Read AI email drafting settings | Includes `api_key_configured`, never returns API keys |
| `PATCH` | `/api/email-settings` | Update AI email drafting settings | Editable: `provider`, `model`, `system_prompt`, `user_prompt` |
| `GET` | `/api/app-settings` | Read operational app settings and environment status | Includes log/scraper/Places defaults and read-only configured/missing status for API keys, drivers, Tor, log/temp paths |
| `PATCH` | `/api/app-settings` | Update operational app settings | Editable: logging verbosity, scraper defaults, scraper max threads, Google Places defaults; never accepts secrets |
| `GET` | `/api/email-settings/business-types` | List business-type email personalization rules | Used by Settings and campaign detail context |
| `PUT` | `/api/email-settings/business-types/<business_type>` | Create/update one business-type email rule | Stores description, pain point, offer angle, extra instructions |
| `GET` | `/api/gmail/status` | Read Gmail integration status | Returns configured/authenticated/account status and safe local paths; never returns tokens |
| `POST` | `/api/gmail/auth/start` | Start Gmail OAuth | Returns Google authorization URL for `gmail.compose` |
| `GET/POST` | `/api/gmail/auth/callback` | Complete Gmail OAuth | Stores refreshable local token in `backend/temp/gmail_token.json` |
| `POST` | `/api/gmail/disconnect` | Disconnect Gmail | Deletes the local Gmail token |
| `POST` | `/api/campaign-leads/<campaign_lead_id>/gmail-draft` | Create one Gmail draft | Uses `final_email` only; does not send email |
| `GET` | `/api/email-category-rules` | List email category auto-marking rules | Returns available categories and rules |
| `PUT` | `/api/email-category-rules/<pattern>` | Create/update an exact local-part category rule | Category must be non-unknown |
| `GET` | `/api/lead-emails/unknown` | List unknown email local-parts | Shows count and example email for rule creation |
| `POST` | `/api/email-category-rules/apply` | Reapply active rules to unknown emails | Updates unknown rows only |
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
- If request fields are omitted, the frontend uses saved `/api/app-settings` Places defaults before submission.

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
- Uses saved `scraper_max_threads` from `/api/app-settings` for the bounded worker pool.
- Captures cleaned visible public homepage text into `website_summary` when useful homepage text is found.
- Summary capture is intentionally simple: it uses the lead website homepage only and does not try about/service/contact fallback pages.
- One-off `/api/scrape/website-emails` remains email-only and does not capture/store website summary context.
- Summary status is stored as `captured`, `empty`, or `failed`; no LLM/API summarization is used.
- Homepage context is HTML-aware: scraper captures page HTML, removes noisy DOM sections such as scripts, nav/header/footer, cookie consent, privacy/policy, newsletter, modal/popup blocks, then stores readable full-body text with headings and list boundaries preserved.
- Page scraping uses a bounded worker-owned Selenium driver pool: the main WebDriver handles homepage summary and sitemap discovery, then each page worker reuses one private WebDriver for multiple URLs and clears cookies/browser storage between pages. With `max_pages=30` and `MAX_THREADS=5`, page scraping starts at most five worker browser sessions instead of one browser per page.

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
| Campaigns | Create campaigns from lead filters, review campaign leads, generate AI drafts, create Gmail drafts from final emails, update stages/priority/notes/final email, export campaign CSV | `/api/campaigns`, `/api/campaigns/<campaign_id>`, `/api/campaigns/<campaign_id>/leads`, `/api/campaign-leads/<campaign_lead_id>`, `/api/campaign-leads/<campaign_lead_id>/generate-email`, `/api/campaign-leads/<campaign_lead_id>/gmail-draft`, `/api/campaigns/<campaign_id>/generate-emails`, `/api/campaigns/<campaign_id>/export` |
| Jobs | List/filter job history, select job details, stop running jobs | `/api/jobs`, `/api/progress/<job_id>`, `/api/stop/<job_id>` |
| Email Rules | Review unknown email local-parts, create exact local-part category rules, and reapply rules to unknown emails | `/api/email-category-rules`, `/api/lead-emails/unknown` |
| Settings | Configure AI drafting, Gmail OAuth connection, operational defaults, logging verbosity, scraper defaults, Google Places defaults, environment status, and business-type personalization rules | `/api/email-settings`, `/api/gmail/status`, `/api/gmail/auth/start`, `/api/gmail/disconnect`, `/api/app-settings`, `/api/email-settings/business-types`, `/api/leads/filter-options` |

Frontend API clients:
- `frontend/src/api/httpClient.ts`: fetch wrapper, base URLs, `ApiError`, download helper.
- `frontend/src/api/healthApi.ts`: backend health.
- `frontend/src/api/scrapingApi.ts`: scrape mutations.
- `frontend/src/api/jobsApi.ts`: job list, progress, stop.
- `frontend/src/api/leadsApi.ts`: lead list, patch, export.
- `frontend/src/api/summaryApi.ts`: dashboard summary.
- `frontend/src/api/emailSettingsApi.ts`: AI email settings, operational app settings, and business-type personalization rules.
- `frontend/src/api/emailRulesApi.ts`: email category rule management and unknown local-part review.
- `frontend/src/api/gmailApi.ts`: Gmail status, OAuth start, disconnect, and campaign lead Gmail draft creation.
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
- `useEmailSettings()`
- `useAppSettings()`
- `useUpdateAppSettings()`
- `useBusinessTypeEmailRules()`
- `useGenerateCampaignLeadEmail()`
- `useGenerateCampaignEmails()`
- `useGmailStatus()`
- `useStartGmailAuth()`
- `useDisconnectGmail()`
- `useCreateCampaignLeadGmailDraft()`
- `useEmailCategoryRules()`
- `useUnknownEmailLocalParts()`
- `useApplyEmailCategoryRules()`

## Current UI Behavior

### UI State Persistence

The frontend uses a hybrid persistence model:
- React Router owns page navigation. Refreshing a browser page keeps the user on the same route instead of resetting to Dashboard.
- URL query parameters own shareable operational state such as scrape form inputs, lead filters, job filters, campaign filters, selected campaign/lead/job IDs, pagination, and page size where implemented.
- `localStorage` owns durable UI preferences such as collapsed sidebar state and preferred lead table page size.
- `sessionStorage` owns temporary work-in-progress drafts such as campaign creation text.

Do not store API keys or secrets in URL params, `localStorage`, or `sessionStorage`.

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

### Campaigns Page

Supports:
- `Generate visible drafts` batch-generates drafts for the current visible campaign lead filter/search set, capped by the request limit. It skips approved leads and final workflow stages (`contacted`, `replied`, `closed`, `skipped`, `do_not_contact`) so approved copy is not accidentally regenerated in bulk.
- The per-lead expanded `Generate draft` button can still regenerate an approved lead draft intentionally. Generated drafts never overwrite `final_email`.
- The expanded campaign lead detail can create one Gmail draft from `final_email` after Gmail is connected in Settings. It requires a valid recipient email and does not send mail automatically. It stores Gmail draft metadata on `campaign_leads` and leaves generated/final email text unchanged.

### Gmail Draft Integration

Behavior:
- Gmail OAuth uses local files only: `config/gmail_client_secret.json` for the Google OAuth client and `backend/temp/gmail_token.json` for the connected account token.
- The requested scope is `https://www.googleapis.com/auth/gmail.compose`.
- The OAuth flow uses Flask callback `GET /api/gmail/auth/callback`; Google Cloud must have `http://localhost:5000/api/gmail/auth/callback` registered as an authorized redirect URI for the default dev server setup.
- `backend/gmail_service.py` persists the OAuth `state`, `redirect_uri`, and PKCE `code_verifier` in `backend/temp/gmail_oauth_state.json` between auth start and callback. Without the stored verifier, Google returns `(invalid_grant) Missing code verifier`.
- `POST /api/campaign-leads/<campaign_lead_id>/gmail-draft` uses only reviewed `final_email`; `email_draft` is never sent to Gmail directly.
- Gmail draft subjects are generated through the existing AI email provider settings at draft-creation time, using `final_email` plus lead/campaign/business-rule context. The subject is stored in `campaign_leads.gmail_subject`.
- Subject generation prompts must return one concise subject only, use a curiosity-driven sales tone, include the contact/lead name naturally when present, avoid polished corporate wording, avoid spammy/clickbait wording, avoid invented claims, and should vary from generic templates such as `Quick question`.
- Gmail draft creation is blocked for `contacted`, `closed`, `skipped`, and `do_not_contact` campaign stages.
- Successful Gmail draft creation stores `gmail_subject`, `gmail_draft_id`, `gmail_message_id`, `gmail_draft_status='created'`, and `gmail_drafted_at`, and advances earlier stages to `approved`.
- Gmail failures store `gmail_draft_status='failed'` and a short `gmail_error`; token material and email bodies should not be logged.
- If Gmail status or draft creation logs `accessNotConfigured`, enable the Gmail API in the same Google Cloud project as the OAuth client and wait a few minutes for propagation.

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

- Logs use one main daily rotating file with bracketed source tags such as `[api]`, `[places]`, `[LLM]`, `[database]`, `[enrichment]`, `[selenium]`, `[jobs]`, and fallback `[app]`.
- `setup_logging()` also writes focused daily rotating files in `backend/log_files/`: `LLM_*.log` for `[LLM]`, `Enrichment_*.log` for `[enrichment]`, and `Errors_*.log` for all `WARNING`/`ERROR`/`CRITICAL` records.
- `config/logging.py` owns tag assignment through `LogTagFilter`; it maps module paths/logger names to tags and also supports explicit `extra={"log_tag": "..."}` overrides.
- `TaggedFormatter` omits filenames for `INFO` logs and includes filenames for `DEBUG`, `WARNING`, `ERROR`, and `CRITICAL` logs.
- `@log_function_call` wraps API functions. In a Flask request context, `INFO` logs only method and path, while `DEBUG` logs sanitized request and response details.
- API request logging is only emitted once for actual route handlers; decorated helper/database calls inside a request must not repeat the same `METHOD /path` line.
- Decorated function debug logs omit raw arguments and raw return values to avoid logging prompts, generated emails, website summaries, lead records, or other large/sensitive payloads.
- Werkzeug access logs are suppressed below `WARNING` because custom `[api]` request logs already record the route path.
- API `DEBUG` response logs summarize or omit verbose fields such as `email_draft`, `final_email`, `website_summary`, `leads`, `emails`, `system_prompt`, and `user_prompt`.
- Google Places HTTP calls log requested endpoint URLs at `INFO`; sanitized request/response details, including redacted API keys, are logged at `DEBUG`.
- LLM provider calls log provider/model/URL at `INFO`; sanitized request/response metadata is logged at `DEBUG` without API keys, prompts, or generated email bodies.
- `@log_all_methods` wraps every method on decorated classes, currently used on `Database`.
- Log files rotate at 100 MB and are stored in `backend/log_files/`.
- `backend/app.py` reconfigures stdout/stderr as UTF-8 with replacement to avoid Windows console logging failures for Google Places names containing special Unicode.
- Selenium WebDriver page-load and script timeouts are set to 12 seconds to keep dead or slow pages from blocking lead enrichment for too long.

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `GOOGLE_API_KEY` | none | Required for Google Places scraping |
| `OPENAI_API_KEY` | none | Required when AI email provider is `openai` |
| `ANTHROPIC_API_KEY` | none | Required when AI email provider is `anthropic` |
| `LOG_LEVEL` | `INFO` | App log level |
| `MAX_THREADS` | `5` | Max concurrent email scraping threads |
| `GMAIL_CLIENT_SECRET_PATH` | `config/gmail_client_secret.json` | Optional override for the local Gmail OAuth client JSON |
| `GMAIL_TOKEN_PATH` | `backend/temp/gmail_token.json` | Optional override for the local Gmail OAuth user token |
| `TOR_EXECUTABLE` | OS-specific path | Path to Tor binary |
| `LIBRARY_LOG_LEVELS` | JSON map | Per-library log suppression |

## Known Tech Debt and Limitations

- No authentication is implemented. This is fine for local personal use, but do not expose publicly without auth, request caps, and rate limiting.
- `/api/scrape/google-maps` is synchronous in code, despite some older README/Postman wording saying async.
- `radius` is accepted by `/api/scrape/google-maps` but ignored by the current Google Places Text Search implementation.
- Frontend is concentrated in `frontend/src/App.tsx`. If the UI grows further, split pages/components into separate files.
- Clipboard features use `navigator.clipboard`, which works on localhost/secure contexts.
- Gmail draft creation depends on local Google Cloud OAuth setup: Gmail API enabled, redirect URI registered, and the Gmail account added as a test user while the consent screen is in Testing mode.
- Manual lead editing supports website, legacy emails string, scrape status, lead flag, lead review status, notes, and captured website context.
- URL non-business filtering is exact-domain/subdomain based. For example, `booking.com` and `www.booking.com` are blocked, but unrelated legitimate `.co.uk` business sites are not blocked merely because another blocked marketplace domain also uses `.co.uk`.

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

Existing comma-separated `leads.emails` data is backfilled into `lead_emails` by the versioned DB initialization migration. The old `leads.emails` field remains for compatibility and CSV export. When normalized email rows are added, updated, or deleted, `leads.emails` is synced from usable rows, excluding `invalid` and `do_not_use`.

Additional endpoints:
- `GET /api/leads/<lead_id>/emails`
- `POST /api/leads/<lead_id>/emails`
- `PATCH /api/lead-emails/<email_id>`
- `DELETE /api/lead-emails/<email_id>`

`GET /api/leads` also supports `lead_flag` and `lead_status` filters.

Email categories:
- `unknown`, `booking`, `info`, `sales`, `support`, `accounting`, `finance`, `events`, `hr`, `marketing`, `manager`, `reception`.

Lead detail UI now supports:
- Editing lead flag, review status, notes, and captured website context.
- Reviewing individual emails.
- Setting email category/status.
- Marking one primary email.
- Adding manual emails.
- Deleting bad emails.
- Email review rows are vertically stacked in the narrow lead detail panel so long email addresses remain readable; controls appear below the email text.
- Captured website context is shown in the lead detail panel with summary status, source URL, and last summary update timestamp.

## Email Category Rule Workflow

The Email Rules tab manages deterministic auto-marking of generic emails.

Current behavior:
- Scraped and manually inserted normalized email rows are automatically categorized by exact local-part rules when their category is empty or `unknown`.
- Examples: `info@domain.com` -> `info`, `finance@domain.com` -> `finance`, `events@domain.com` -> `events`, `reservation@domain.com` -> `booking`.
- Personal-name emails remain `unknown` unless a user intentionally creates a matching rule.
- The Email Rules tab lists unknown local-parts with counts and example addresses.
- Users can promote an unknown local-part into a category rule.
- Users can manually add a rule by typing a local-part and selecting a category.
- The `Reapply rules` action applies active rules to currently unknown emails only.
- Existing manually reviewed/non-unknown categories are not overwritten by rule application.

## Campaign Workflow

Campaigns are a workflow layer over existing leads. Lead records remain the source of truth for business/contact data. Campaign stages are campaign-specific, with one intentional sync: when a campaign lead is marked `contacted`, the linked base lead's `lead_status` is also set to `contacted`. Existing contacted campaign memberships are backfilled on startup unless the base lead is already `do_not_contact`.

Current behavior:
- Campaigns are created from filters matching `/api/leads`, including scrape status, email/website/phone presence, lead flag, lead review status, business type, and search location.
- Campaign creation uses live dropdowns for business type and search location from `/api/leads/filter-options`, parsed from existing scraped `leads.location` values like `dentist:London, UK`. The endpoint returns distinct business type counts, distinct location counts, and business type/location pair counts. The frontend uses those pair counts to make the two dropdowns dependent: selecting a business type narrows locations to only locations scraped for that type, selecting a location narrows business types to only types scraped there, and option labels show counts.
- Campaign creation stores the filters JSON and links matching leads in `campaign_leads` with initial stage `review`.
- Leads can belong to multiple campaigns; `/api/leads` includes `campaign_count`, `campaign_names`, and detailed `campaign_memberships`.
- The Leads tab shows a Campaign column and expanded lead details list campaign memberships.
- The Campaigns tab lists campaigns, creates campaigns, opens campaign detail, filters campaign leads by stage/search, updates stage and priority inline, edits campaign notes/email draft/final email, marks leads contacted, and exports campaign CSV. Marking a campaign lead contacted also marks the global lead review status as `contacted`.
- Campaign detail stage counts are interactive buttons. Selecting a stage button filters the campaign lead table to that exact stage; selecting `All` shows every campaign lead. When a lead is moved from one stage to another, it should disappear from the previous active stage view after the campaign lead query refreshes.

## AI-Assisted Campaign Email Drafting

AI email drafting is part of the Campaigns workflow, not an automatic sending system.

Current behavior:
- Settings tab manages provider (`openai` or `anthropic`), provider-aware curated model dropdowns with a custom model ID fallback, system prompt, user prompt/template, operational defaults, logging verbosity, and per-business-type personalization rules.
- Provider API keys are read server-side from `.env` as `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`. The frontend only receives `api_key_configured`.
- Operational Settings also shows read-only environment status for Google/OpenAI/Anthropic API keys, Tor/driver availability, log path, and temp path. Secrets and local binary paths are not editable from the UI.
- A single campaign lead draft can be generated from the expanded campaign lead row.
- Visible/filtered campaign leads can be batch-generated from the campaign detail toolbar.
- Generation uses campaign lead context: lead name, business type, location, address, phone, website, usable email, website summary, campaign notes, existing draft/final email, and the matching business-type email rule.
- Generated text is stored in `campaign_leads.email_draft`.
- Generation never overwrites `campaign_leads.final_email`.
- Successful generation moves eligible leads to `drafted`; it does not move leads already in `approved`, `contacted`, `replied`, `closed`, `skipped`, or `do_not_contact`.
- Leads without a usable email, leads with base `lead_status='do_not_contact'`, and blocked campaign stages are not eligible for generation.
- Human review remains required: users edit `email_draft`, save `final_email`, approve, copy draft/final email text, and mark contacted manually.

Implementation notes:
- `backend/ai_email_service.py` wraps OpenAI Chat Completions and Anthropic Messages behind `generate_email_draft()`.
- The saved Settings user prompt/template is sent as the primary email structure. The prompt explicitly tells the model to preserve the template's intent, call-to-action, sign-off, and flow, then use structured lead/campaign data beneath it.
- Routes keep API keys server-side and return clear errors for unsupported providers, missing keys, blocked leads, and provider failures.
- Batch generation is synchronous and capped by request `limit` (default 25, max 100); use it for small local batches.
