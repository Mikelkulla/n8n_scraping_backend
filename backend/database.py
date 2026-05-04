import sqlite3
import os
import logging
import threading
import json
from backend.app_settings import Config
from config.logging import log_all_methods

DEFAULT_EMAIL_SYSTEM_PROMPT = """You write concise, professional outreach email drafts for manual review.
Use only the supplied lead, campaign, website context, and business-type rule.
Do not invent claims, metrics, client names, or details that are not provided.
Avoid spammy wording, pressure tactics, and exaggerated promises.
Return only the email body."""

DEFAULT_EMAIL_USER_PROMPT = """Write a personalized outreach email for this lead.

Template:
Hi [Name],

I saw you're [specific description about their business].

Usually companies at this stage struggle with [very specific problem].

I've built systems that:

* Automatically qualify leads by asking targeted questions and tagging them in Airtable/CRM based on their responses
* Automate business workflows using Google Apps Script to connect tools, streamline data processing, and reduce manual tasks across operations

Looking at your setup, I already see a couple of areas where automation could save serious time.

If you're open to it, we can jump on a quick 15-minute call and I'll walk you through exactly what I'd improve and how it would work for your case.

Looking forward!

Prof. MSc. Mikel Kulla"""

DEFAULT_EMAIL_SETTINGS = {
    "ai_email_provider": "openai",
    "ai_email_model": "gpt-4o-mini",
    "ai_email_system_prompt": DEFAULT_EMAIL_SYSTEM_PROMPT,
    "ai_email_user_prompt": DEFAULT_EMAIL_USER_PROMPT,
}

EMAIL_CATEGORY_VALUES = {
    "unknown",
    "booking",
    "info",
    "sales",
    "support",
    "accounting",
    "finance",
    "events",
    "hr",
    "marketing",
    "manager",
    "reception",
}

DEFAULT_EMAIL_CATEGORY_RULES = [
    ("info", "info"),
    ("sales", "sales"),
    ("support", "support"),
    ("accounting", "accounting"),
    ("accounts", "accounting"),
    ("finance", "finance"),
    ("billing", "finance"),
    ("event", "events"),
    ("events", "events"),
    ("booking", "booking"),
    ("bookings", "booking"),
    ("reservation", "booking"),
    ("reservations", "booking"),
    ("reserve", "booking"),
    ("manager", "manager"),
    ("management", "manager"),
    ("reception", "reception"),
    ("frontdesk", "reception"),
    ("front-desk", "reception"),
    ("hr", "hr"),
    ("jobs", "hr"),
    ("careers", "hr"),
    ("marketing", "marketing"),
]

CURRENT_SCHEMA_VERSION = 1

@log_all_methods
class Database:
    """Manages the application's SQLite database connection and operations.

    This class provides a thread-safe interface for all database interactions,
    including initializing the database schema, inserting and updating job
    and lead records. It can be used as a context manager to automatically
    handle connection and transaction management.

    Attributes:
        db_path (str): The file path to the SQLite database.
    """
    _lock = threading.RLock()

    def __init__(self, db_path=None):
        """Initializes the Database instance.

        Args:
            db_path (str, optional): The path to the database file. If not
                provided, it defaults to 'scraping.db' in the temporary
                directory defined in `Config`.
        """
        if db_path is None:
            self.db_path = os.path.join(Config.TEMP_PATH, "scraping.db")
        else:
            self.db_path = db_path
        self.conn = None
        self.cursor = None
        self._initialize_memory_connections = False

    def initialize(self):
        """Runs schema creation and versioned migrations for this database."""
        if self.db_path == ':memory:':
            self._initialize_memory_connections = True
            return self
        self._init_db()
        return self

    def _init_db(self):
        """
        Initialize the SQLite database and run pending migrations.
        """
        conn = None
        try:
            # For in-memory databases, no directory creation is needed
            if self.db_path != ':memory:':
                db_dir = os.path.dirname(self.db_path)
                if db_dir:
                    os.makedirs(db_dir, exist_ok=True)
                    if not os.access(db_dir, os.W_OK):
                        raise PermissionError(f"No write permission for {db_dir}")

            # Connect to the database to create tables
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Enable foreign key support
            cursor.execute("PRAGMA foreign_keys = ON")

            cursor.execute("PRAGMA user_version")
            user_version = cursor.fetchone()[0]
            if user_version < CURRENT_SCHEMA_VERSION:
                self._migrate_to_v1(cursor)
                cursor.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION}")

            conn.commit()
            logging.info(f"Database initialized at {self.db_path}")
        except (sqlite3.Error, PermissionError, OSError) as e:
            logging.error(f"Failed to initialize database: {e}")
        finally:
            if conn:
                conn.close()

    def _migrate_to_v1(self, cursor):
        """Creates the current schema and migrates pre-versioned databases."""
        # Create job_executions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS job_executions (
                execution_id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                step_id TEXT NOT NULL,
                input TEXT NOT NULL,
                max_pages INTEGER,
                use_tor BOOLEAN,
                headless BOOLEAN,
                status TEXT NOT NULL,
                current_row INTEGER,
                total_rows INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                error_message TEXT,
                stop_call BOOLEAN DEFAULT FALSE,
                UNIQUE(job_id, step_id)
            )
        """)
        self._add_missing_columns(cursor, "job_executions", {
            "max_pages": "INTEGER",
            "use_tor": "BOOLEAN",
            "headless": "BOOLEAN",
            "current_row": "INTEGER",
            "total_rows": "INTEGER",
            "created_at": "TIMESTAMP",
            "updated_at": "TIMESTAMP",
            "error_message": "TEXT",
            "stop_call": "BOOLEAN DEFAULT FALSE",
        })

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                lead_id INTEGER PRIMARY KEY AUTOINCREMENT,
                execution_id INTEGER NOT NULL,
                place_id TEXT NOT NULL,
                location TEXT,
                name TEXT,
                address TEXT,
                phone TEXT,
                website TEXT,
                emails TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT,
                UNIQUE(place_id),
                FOREIGN KEY (execution_id) REFERENCES job_executions(execution_id)
            )
        """)

        self._add_missing_columns(cursor, "leads", {
            "location": "TEXT",
            "name": "TEXT",
            "address": "TEXT",
            "phone": "TEXT",
            "created_at": "TIMESTAMP",
            "updated_at": "TIMESTAMP",
            "lead_flag": "TEXT DEFAULT 'needs_review'",
            "lead_status": "TEXT DEFAULT 'new'",
            "notes": "TEXT",
            "website_summary": "TEXT",
            "summary_source_url": "TEXT",
            "summary_status": "TEXT",
            "summary_updated_at": "TIMESTAMP"
        })

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS lead_emails (
                email_id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id INTEGER NOT NULL,
                email TEXT NOT NULL,
                category TEXT DEFAULT 'unknown',
                status TEXT DEFAULT 'new',
                is_primary BOOLEAN DEFAULT FALSE,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(lead_id, email),
                FOREIGN KEY (lead_id) REFERENCES leads(lead_id) ON DELETE CASCADE
            )
        """)
        self._add_missing_columns(cursor, "lead_emails", {
            "category": "TEXT DEFAULT 'unknown'",
            "status": "TEXT DEFAULT 'new'",
            "is_primary": "BOOLEAN DEFAULT FALSE",
            "notes": "TEXT",
            "created_at": "TIMESTAMP",
            "updated_at": "TIMESTAMP",
        })

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS email_category_rules (
                rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern TEXT NOT NULL,
                match_type TEXT NOT NULL DEFAULT 'local_part_exact',
                category TEXT NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(pattern, match_type)
            )
        """)

        for pattern, category in DEFAULT_EMAIL_CATEGORY_RULES:
            cursor.execute("""
                INSERT OR IGNORE INTO email_category_rules (
                    pattern, match_type, category, is_active, updated_at
                ) VALUES (?, 'local_part_exact', ?, TRUE, CURRENT_TIMESTAMP)
            """, (pattern, category))

        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS classify_lead_email_after_insert
            AFTER INSERT ON lead_emails
            WHEN NEW.category IS NULL OR NEW.category = '' OR NEW.category = 'unknown'
            BEGIN
                UPDATE lead_emails
                SET category = (
                    SELECT category
                    FROM email_category_rules
                    WHERE is_active = TRUE
                      AND match_type = 'local_part_exact'
                      AND pattern = LOWER(SUBSTR(NEW.email, 1, INSTR(NEW.email, '@') - 1))
                    LIMIT 1
                ),
                updated_at = CURRENT_TIMESTAMP
                WHERE email_id = NEW.email_id
                  AND EXISTS (
                    SELECT 1
                    FROM email_category_rules
                    WHERE is_active = TRUE
                      AND match_type = 'local_part_exact'
                      AND pattern = LOWER(SUBSTR(NEW.email, 1, INSTR(NEW.email, '@') - 1))
                  );
            END
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS campaigns (
                campaign_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                business_type TEXT,
                search_location TEXT,
                filters_json TEXT,
                status TEXT DEFAULT 'draft',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self._add_missing_columns(cursor, "campaigns", {
            "business_type": "TEXT",
            "search_location": "TEXT",
            "filters_json": "TEXT",
            "status": "TEXT DEFAULT 'draft'",
            "notes": "TEXT",
            "created_at": "TIMESTAMP",
            "updated_at": "TIMESTAMP",
        })

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS campaign_leads (
                campaign_lead_id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id INTEGER NOT NULL,
                lead_id INTEGER NOT NULL,
                stage TEXT NOT NULL DEFAULT 'review',
                priority TEXT,
                email_draft TEXT,
                final_email TEXT,
                campaign_notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                contacted_at TIMESTAMP,
                UNIQUE(campaign_id, lead_id),
                FOREIGN KEY (campaign_id) REFERENCES campaigns(campaign_id) ON DELETE CASCADE,
                FOREIGN KEY (lead_id) REFERENCES leads(lead_id) ON DELETE CASCADE
            )
        """)
        self._add_missing_columns(cursor, "campaign_leads", {
            "priority": "TEXT",
            "email_draft": "TEXT",
            "final_email": "TEXT",
            "campaign_notes": "TEXT",
            "created_at": "TIMESTAMP",
            "updated_at": "TIMESTAMP",
            "contacted_at": "TIMESTAMP",
        })

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS lead_discoveries (
                discovery_id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id INTEGER NOT NULL,
                execution_id INTEGER NOT NULL,
                place_id TEXT NOT NULL,
                location TEXT,
                business_type TEXT,
                search_location TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(lead_id, execution_id),
                FOREIGN KEY (lead_id) REFERENCES leads(lead_id) ON DELETE CASCADE,
                FOREIGN KEY (execution_id) REFERENCES job_executions(execution_id) ON DELETE CASCADE
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS business_type_email_rules (
                business_type TEXT PRIMARY KEY,
                business_description TEXT,
                pain_point TEXT,
                offer_angle TEXT,
                extra_instructions TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        for key, value in DEFAULT_EMAIL_SETTINGS.items():
            cursor.execute("""
                INSERT OR IGNORE INTO app_settings (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (key, value))

        self._migrate_global_lead_uniqueness(cursor)

    def _add_missing_columns(self, cursor, table_name, columns):
        cursor.execute(f"PRAGMA table_info({table_name})")
        existing_columns = {row[1] for row in cursor.fetchall()}
        for column, definition in columns.items():
            if column not in existing_columns:
                cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column} {definition}")

    def _split_lead_location(self, location):
        """Parses stored lead location strings such as 'dentist:London, UK'."""
        if not isinstance(location, str) or not location.strip():
            return None, None

        if ":" in location:
            business_type, search_location = location.split(":", 1)
            business_type = business_type.strip() or None
            search_location = search_location.strip() or None
            return business_type, search_location

        return None, location.strip() or None

    def _is_blank(self, value):
        return value is None or str(value).strip() == ""

    def _stage_rank(self, stage):
        ranks = {
            "review": 1,
            "ready_for_email": 2,
            "drafted": 3,
            "approved": 4,
            "contacted": 5,
            "replied": 6,
            "closed": 7,
            "skipped": 2,
            "do_not_contact": 5,
        }
        return ranks.get(stage or "", 0)

    def _lead_status_rank(self, status):
        ranks = {
            "new": 1,
            "reviewed": 2,
            "ready": 3,
            "contacted": 4,
            "do_not_contact": 5,
        }
        return ranks.get(status or "", 0)

    def _lead_flag_rank(self, flag):
        ranks = {
            "needs_review": 1,
            "bad": 2,
            "good": 3,
            "hot": 4,
        }
        return ranks.get(flag or "", 0)

    def _scrape_status_rank(self, status):
        ranks = {
            "pending": 1,
            "skipped": 2,
            "failed": 3,
            "scraped": 4,
        }
        return ranks.get(status or "", 0)

    def _record_lead_discovery_with_cursor(self, cursor, lead_id, execution_id, place_id, location):
        business_type, search_location = self._split_lead_location(location)
        cursor.execute("""
            INSERT INTO lead_discoveries (
                lead_id, execution_id, place_id, location, business_type, search_location, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(lead_id, execution_id) DO UPDATE SET
                place_id = excluded.place_id,
                location = COALESCE(excluded.location, lead_discoveries.location),
                business_type = COALESCE(excluded.business_type, lead_discoveries.business_type),
                search_location = COALESCE(excluded.search_location, lead_discoveries.search_location),
                updated_at = CURRENT_TIMESTAMP
        """, (lead_id, execution_id, place_id, location, business_type, search_location))

    def _lead_uniqueness_is_global(self, cursor):
        cursor.execute("PRAGMA index_list(leads)")
        for index in cursor.fetchall():
            is_unique = index["unique"] if "unique" in index.keys() else index[2]
            index_name = index["name"] if "name" in index.keys() else index[1]
            if not is_unique:
                continue
            cursor.execute(f"PRAGMA index_info({index_name})")
            columns = [row["name"] if "name" in row.keys() else row[2] for row in cursor.fetchall()]
            if columns == ["place_id"]:
                return True
        return False

    def _canonical_lead_sort_key(self, lead, campaign_counts):
        valuable_fields = [
            "emails",
            "website_summary",
            "notes",
            "website",
            "phone",
            "address",
        ]
        valuable_count = sum(0 if self._is_blank(lead[field]) else 1 for field in valuable_fields)
        return (
            1 if campaign_counts.get(lead["lead_id"], 0) else 0,
            self._lead_status_rank(lead["lead_status"]),
            valuable_count,
            1 if lead["status"] == "scraped" else 0,
            -lead["lead_id"],
        )

    def _merge_campaign_lead_rows(self, cursor, canonical_id, duplicate_id):
        cursor.execute("""
            SELECT *
            FROM campaign_leads
            WHERE lead_id = ?
        """, (duplicate_id,))
        duplicate_memberships = cursor.fetchall()

        for duplicate in duplicate_memberships:
            cursor.execute("""
                SELECT *
                FROM campaign_leads
                WHERE campaign_id = ? AND lead_id = ?
            """, (duplicate["campaign_id"], canonical_id))
            canonical = cursor.fetchone()

            if not canonical:
                cursor.execute("""
                    UPDATE campaign_leads
                    SET lead_id = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE campaign_lead_id = ?
                """, (canonical_id, duplicate["campaign_lead_id"]))
                continue

            updates = {}
            if self._stage_rank(duplicate["stage"]) > self._stage_rank(canonical["stage"]):
                updates["stage"] = duplicate["stage"]

            for field in ["priority", "email_draft", "final_email", "campaign_notes", "contacted_at"]:
                if self._is_blank(canonical[field]) and not self._is_blank(duplicate[field]):
                    updates[field] = duplicate[field]

            if updates:
                set_clause = ", ".join(f"{field} = ?" for field in updates)
                params = list(updates.values()) + [canonical["campaign_lead_id"]]
                cursor.execute(f"""
                    UPDATE campaign_leads
                    SET {set_clause}, updated_at = CURRENT_TIMESTAMP
                    WHERE campaign_lead_id = ?
                """, params)

            cursor.execute("""
                DELETE FROM campaign_leads
                WHERE campaign_lead_id = ?
            """, (duplicate["campaign_lead_id"],))

    def _merge_lead_email_rows(self, cursor, canonical_id, duplicate_id):
        cursor.execute("""
            SELECT *
            FROM lead_emails
            WHERE lead_id = ?
            ORDER BY is_primary DESC, email_id ASC
        """, (duplicate_id,))
        duplicate_emails = cursor.fetchall()

        cursor.execute("""
            SELECT COUNT(*) AS count
            FROM lead_emails
            WHERE lead_id = ? AND is_primary = TRUE
        """, (canonical_id,))
        canonical_has_primary = (cursor.fetchone()["count"] or 0) > 0

        for duplicate in duplicate_emails:
            cursor.execute("""
                SELECT *
                FROM lead_emails
                WHERE lead_id = ? AND email = ?
            """, (canonical_id, duplicate["email"]))
            existing = cursor.fetchone()

            if not existing:
                is_primary = bool(duplicate["is_primary"]) and not canonical_has_primary
                cursor.execute("""
                    INSERT INTO lead_emails (
                        lead_id, email, category, status, is_primary, notes, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    canonical_id,
                    duplicate["email"],
                    duplicate["category"],
                    duplicate["status"],
                    is_primary,
                    duplicate["notes"],
                    duplicate["created_at"],
                ))
                canonical_has_primary = canonical_has_primary or is_primary
                continue

            updates = {}
            if existing["category"] in (None, "", "unknown") and duplicate["category"] not in (None, "", "unknown"):
                updates["category"] = duplicate["category"]
            if existing["status"] in (None, "", "new") and duplicate["status"] not in (None, "", "new"):
                updates["status"] = duplicate["status"]
            if self._is_blank(existing["notes"]) and not self._is_blank(duplicate["notes"]):
                updates["notes"] = duplicate["notes"]
            if bool(duplicate["is_primary"]) and not canonical_has_primary:
                updates["is_primary"] = True
                canonical_has_primary = True

            if updates:
                set_clause = ", ".join(f"{field} = ?" for field in updates)
                params = list(updates.values()) + [existing["email_id"]]
                cursor.execute(f"""
                    UPDATE lead_emails
                    SET {set_clause}, updated_at = CURRENT_TIMESTAMP
                    WHERE email_id = ?
                """, params)

        cursor.execute("DELETE FROM lead_emails WHERE lead_id = ?", (duplicate_id,))

    def _merge_duplicate_lead_into_canonical(self, cursor, canonical, duplicate):
        canonical_id = canonical["lead_id"]
        duplicate_id = duplicate["lead_id"]

        self._record_lead_discovery_with_cursor(
            cursor,
            canonical_id,
            duplicate["execution_id"],
            duplicate["place_id"],
            duplicate["location"],
        )
        self._merge_lead_email_rows(cursor, canonical_id, duplicate_id)
        self._merge_campaign_lead_rows(cursor, canonical_id, duplicate_id)

        updates = {}
        fill_fields = [
            "location",
            "name",
            "address",
            "phone",
            "website",
            "emails",
            "notes",
            "website_summary",
            "summary_source_url",
            "summary_status",
            "summary_updated_at",
        ]
        for field in fill_fields:
            if self._is_blank(canonical[field]) and not self._is_blank(duplicate[field]):
                updates[field] = duplicate[field]

        if self._scrape_status_rank(duplicate["status"]) > self._scrape_status_rank(canonical["status"]):
            updates["status"] = duplicate["status"]
        if self._lead_status_rank(duplicate["lead_status"]) > self._lead_status_rank(canonical["lead_status"]):
            updates["lead_status"] = duplicate["lead_status"]
        if self._lead_flag_rank(duplicate["lead_flag"]) > self._lead_flag_rank(canonical["lead_flag"]):
            updates["lead_flag"] = duplicate["lead_flag"]
        if not self._is_blank(canonical["notes"]) and not self._is_blank(duplicate["notes"]) and duplicate["notes"] not in canonical["notes"]:
            updates["notes"] = f"{canonical['notes']}\n\n{duplicate['notes']}"

        if updates:
            set_clause = ", ".join(f"{field} = ?" for field in updates)
            params = list(updates.values()) + [canonical_id]
            cursor.execute(f"""
                UPDATE leads
                SET {set_clause}, updated_at = CURRENT_TIMESTAMP
                WHERE lead_id = ?
            """, params)
            canonical.update(updates)

        cursor.execute("DELETE FROM leads WHERE lead_id = ?", (duplicate_id,))

    def _sync_lead_emails_string_with_cursor(self, cursor, lead_id):
        cursor.execute("""
            SELECT email
            FROM lead_emails
            WHERE lead_id = ?
              AND status NOT IN ('invalid', 'do_not_use')
            ORDER BY is_primary DESC, email_id ASC
        """, (lead_id,))
        emails = [row["email"] for row in cursor.fetchall()]
        emails_str = ",".join(emails) if emails else None
        cursor.execute("""
            UPDATE leads
            SET emails = ?, updated_at = CURRENT_TIMESTAMP
            WHERE lead_id = ?
        """, (emails_str, lead_id))

    def _backfill_lead_emails_from_string_with_cursor(self, cursor, lead_id, emails):
        parsed_emails = [
            email.strip()
            for email in str(emails or "").split(",")
            if email.strip()
        ]
        for index, email in enumerate(parsed_emails):
            cursor.execute("""
                INSERT OR IGNORE INTO lead_emails (
                    lead_id, email, category, status, is_primary
                ) VALUES (?, ?, 'unknown', 'new', ?)
            """, (lead_id, email, index == 0))

    def _migrate_global_lead_uniqueness(self, cursor):
        """Backfills discovery history and enforces one canonical lead per place_id."""
        cursor.execute("""
            SELECT l.*, COUNT(cl.campaign_lead_id) AS campaign_count
            FROM leads l
            LEFT JOIN campaign_leads cl ON l.lead_id = cl.lead_id
            GROUP BY l.lead_id
            ORDER BY l.created_at ASC, l.lead_id ASC
        """)
        leads = [dict(row) for row in cursor.fetchall()]
        if not leads:
            if not self._lead_uniqueness_is_global(cursor):
                cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_leads_unique_place_id ON leads(place_id)")
            return

        for lead in leads:
            self._backfill_lead_emails_from_string_with_cursor(cursor, lead["lead_id"], lead.get("emails"))
            self._record_lead_discovery_with_cursor(
                cursor,
                lead["lead_id"],
                lead["execution_id"],
                lead["place_id"],
                lead["location"],
            )

        grouped = {}
        for lead in leads:
            grouped.setdefault(lead["place_id"], []).append(lead)

        campaign_counts = {lead["lead_id"]: lead.get("campaign_count") or 0 for lead in leads}
        canonical_ids = set()
        for place_id, group in grouped.items():
            if len(group) == 1:
                canonical_ids.add(group[0]["lead_id"])
                continue

            canonical = max(group, key=lambda item: self._canonical_lead_sort_key(item, campaign_counts))
            canonical_ids.add(canonical["lead_id"])
            for duplicate in group:
                if duplicate["lead_id"] == canonical["lead_id"]:
                    continue
                self._merge_duplicate_lead_into_canonical(cursor, canonical, duplicate)

            self._sync_lead_emails_string_with_cursor(cursor, canonical["lead_id"])

        for lead_id in canonical_ids:
            self._sync_lead_emails_string_with_cursor(cursor, lead_id)

        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_leads_unique_place_id ON leads(place_id)")

    def __enter__(self):
        """Opens a database connection and returns the instance.

        This method is called when entering a `with` statement. It acquires a
        thread lock and establishes a connection to the database.

        Returns:
            Database: The current instance with an active connection.
        """
        Database._lock.acquire()
        self.conn = sqlite3.connect(self.db_path, timeout=10.0)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self.cursor.execute("PRAGMA foreign_keys = ON")
        if self.db_path == ':memory:' and self._initialize_memory_connections:
            self._migrate_to_v1(self.cursor)
            self.cursor.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Closes the database connection and releases the lock.

        This method is called when exiting a `with` statement. It commits any
        successful transactions or rolls back in case of an exception.
        """
        if self.conn:
            if exc_type is None:
                self.conn.commit()
            else:
                self.conn.rollback()
            self.conn.close()
            self.conn = None
        Database._lock.release()

    def insert_job_execution(self, job_id, step_id, input, max_pages=None, use_tor=None, headless=None, status=None, stop_call=False, error_message=None, current_row=None, total_rows=None):
        """Inserts a new job execution record into the database.

        Args:
            job_id (str): The unique identifier for the job.
            step_id (str): The identifier for the specific task.
            input (str): The primary input for the job (e.g., URL).
            max_pages (int, optional): Max pages to scrape. Defaults to None.
            use_tor (bool, optional): Whether Tor was used. Defaults to None.
            headless (bool, optional): Whether browser was headless. Defaults to None.
            status (str, optional): The job's status. Defaults to None.
            stop_call (bool, optional): If a stop was signaled. Defaults to False.
            error_message (str, optional): Error message if any. Defaults to None.
            current_row (int, optional): The current progress counter. Defaults to None.
            total_rows (int, optional): The total items to process. Defaults to None.
        """
        try:
            self.cursor.execute("""
                INSERT INTO job_executions (
                    job_id, step_id, input, max_pages, use_tor, headless, status, stop_call,
                    error_message, current_row, total_rows, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (job_id, step_id, input, max_pages, use_tor, headless, status, stop_call, error_message, current_row, total_rows))
            logging.info(f"Inserted execution for job {job_id}, step {step_id}")
        except sqlite3.Error as e:
            logging.error(f"Failed to insert execution for job {job_id}: {e}")
            raise

    def update_job_execution(self, job_id, step_id, current_row=None, total_rows=None, status=None, error_message=None, stop_call=None):
        """Updates an existing job execution record.

        This method dynamically builds an SQL UPDATE statement to modify only the
        provided fields of a job record.

        Args:
            job_id (str): The unique identifier for the job.
            step_id (str): The identifier for the specific task.
            current_row (int, optional): The new progress counter. Defaults to None.
            total_rows (int, optional): The new total items. Defaults to None.
            status (str, optional): The new status. Defaults to None.
            error_message (str, optional): The new error message. Defaults to None.
            stop_call (bool, optional): The new stop signal status. Defaults to None.
        """
        try:
            set_clauses = []
            params = []
            if current_row is not None:
                set_clauses.append("current_row = ?")
                params.append(current_row)
            if total_rows is not None:
                set_clauses.append("total_rows = ?")
                params.append(total_rows)
            if status is not None:
                set_clauses.append("status = ?")
                params.append(status)
            if error_message is not None:
                set_clauses.append("error_message = ?")
                params.append(error_message)
            if stop_call is not None:
                set_clauses.append("stop_call = ?")
                params.append(stop_call)
            
            set_clauses.append("updated_at = CURRENT_TIMESTAMP")

            if not set_clauses:
                logging.warning(f"No fields to update for job {job_id}, step {step_id}")
                return

            query = f"UPDATE job_executions SET {', '.join(set_clauses)} WHERE job_id = ? AND step_id = ?"
            params.extend([job_id, step_id])

            self.cursor.execute(query, params)
            if self.cursor.rowcount == 0:
                logging.warning(f"No record found to update for job {job_id}, step {step_id}")
            else:
                logging.info(f"Updated execution for job {job_id}, step {step_id}")
        except sqlite3.Error as e:
            logging.error(f"Failed to update execution for job {job_id}: {e}")
            raise

    def get_job_execution(self, job_id, step_id):
        """Retrieves a job execution record from the database.

        Args:
            job_id (str): The unique identifier for the job.
            step_id (str): The identifier for the specific task.

        Returns:
            dict | None: A dictionary representing the job record if found,
            otherwise None.
        """
        try:
            self.cursor.execute("""
                SELECT * FROM job_executions WHERE job_id = ? AND step_id = ?
            """, (job_id, step_id))
            row = self.cursor.fetchone()
            return dict(row) if row else None
        except sqlite3.Error as e:
            logging.error(f"Failed to fetch execution for job {job_id}: {e}")
            return None

    def list_job_executions(self, status=None, step_id=None, limit=50):
        """Retrieves recent job executions with optional filters.

        Args:
            status (str, optional): Exact job status to match.
            step_id (str, optional): Exact step ID to match.
            limit (int, optional): Maximum number of jobs to return.

        Returns:
            list[dict]: Job execution rows ordered by latest update.
        """
        try:
            query = """
                SELECT
                    execution_id,
                    job_id,
                    step_id,
                    input,
                    max_pages,
                    use_tor,
                    headless,
                    status,
                    current_row,
                    total_rows,
                    created_at,
                    updated_at,
                    error_message,
                    stop_call
                FROM job_executions
                WHERE 1 = 1
            """
            params = []

            if status:
                query += " AND status = ?"
                params.append(status)

            if step_id:
                query += " AND step_id = ?"
                params.append(step_id)

            query += " ORDER BY updated_at DESC, execution_id DESC LIMIT ?"
            params.append(limit)

            self.cursor.execute(query, params)
            rows = self.cursor.fetchall()
            return [dict(row) for row in rows] if rows else []
        except sqlite3.Error as e:
            logging.error(f"Failed to list job executions: {e}")
            return []

    def get_summary(self):
        """Computes dashboard summary counts for leads and jobs.

        Returns:
            dict: Aggregated counts for the lead pipeline and job statuses.
        """
        try:
            lead_counts = {
                "total": 0,
                "with_website": 0,
                "with_email": 0,
                "pending_enrichment": 0,
                "scraped": 0,
                "failed": 0,
                "skipped": 0,
            }
            job_counts = {
                "total": 0,
                "running": 0,
                "completed": 0,
                "failed": 0,
                "stopped": 0,
            }

            self.cursor.execute("""
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN website IS NOT NULL AND TRIM(website) != '' THEN 1 ELSE 0 END) AS with_website,
                    SUM(CASE WHEN emails IS NOT NULL AND TRIM(emails) != '' THEN 1 ELSE 0 END) AS with_email,
                    SUM(CASE
                        WHEN website IS NOT NULL
                         AND TRIM(website) != ''
                         AND (status IS NULL OR status != 'scraped')
                        THEN 1 ELSE 0
                    END) AS pending_enrichment,
                    SUM(CASE WHEN status = 'scraped' THEN 1 ELSE 0 END) AS scraped,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed,
                    SUM(CASE WHEN status = 'skipped' THEN 1 ELSE 0 END) AS skipped
                FROM leads
            """)
            lead_row = self.cursor.fetchone()
            if lead_row:
                lead_counts.update({key: lead_row[key] or 0 for key in lead_counts})

            self.cursor.execute("""
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END) AS running,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed,
                    SUM(CASE WHEN status = 'stopped' THEN 1 ELSE 0 END) AS stopped
                FROM job_executions
            """)
            job_row = self.cursor.fetchone()
            if job_row:
                job_counts.update({key: job_row[key] or 0 for key in job_counts})

            return {
                "leads": lead_counts,
                "jobs": job_counts,
            }
        except sqlite3.Error as e:
            logging.error(f"Failed to compute summary: {e}")
            return {
                "leads": {
                    "total": 0,
                    "with_website": 0,
                    "with_email": 0,
                    "pending_enrichment": 0,
                    "scraped": 0,
                    "failed": 0,
                    "skipped": 0,
                },
                "jobs": {
                    "total": 0,
                    "running": 0,
                    "completed": 0,
                    "failed": 0,
                    "stopped": 0,
                },
            }

    def get_leads(self, status_filter=None):
        """Retrieves lead records from the database, joining with job_executions.

        Args:
            status_filter (str, optional): A filter to apply to the lead status.
                If "NOT scraped", it retrieves leads that have not yet been
                processed. Defaults to None.

        Returns:
            list[dict]: A list of dictionaries, where each dictionary represents a lead
            including the `job_id` from the parent execution.
        """
        try:
            query = """
                SELECT l.*, j.job_id
                FROM leads l
                JOIN job_executions j ON l.execution_id = j.execution_id
                WHERE l.website IS NOT NULL
            """
            if status_filter == "NOT scraped":
                query += " AND (l.status IS NULL OR l.status != 'scraped')"
            
            self.cursor.execute(query)
            rows = self.cursor.fetchall()
            return [dict(row) for row in rows] if rows else []
        except sqlite3.Error as e:
            logging.error(f"Failed to fetch leads: {e}")
            return []

    def _attach_campaign_memberships(self, leads):
        """Adds campaign membership summary fields to lead rows."""
        if not leads:
            return []

        lead_ids = [lead["lead_id"] for lead in leads if lead.get("lead_id") is not None]
        if not lead_ids:
            return leads

        placeholders = ",".join("?" for _ in lead_ids)
        self.cursor.execute(f"""
            SELECT
                cl.lead_id,
                c.campaign_id,
                c.name AS campaign_name,
                cl.stage
            FROM campaign_leads cl
            JOIN campaigns c ON cl.campaign_id = c.campaign_id
            WHERE cl.lead_id IN ({placeholders})
            ORDER BY c.updated_at DESC, c.campaign_id DESC
        """, lead_ids)
        memberships_by_lead = {}
        for row in self.cursor.fetchall():
            membership = dict(row)
            memberships_by_lead.setdefault(membership["lead_id"], []).append(membership)

        for lead in leads:
            memberships = memberships_by_lead.get(lead.get("lead_id"), [])
            lead["campaign_memberships"] = memberships
            lead["campaign_count"] = len(memberships)
            lead["campaign_names"] = [item["campaign_name"] for item in memberships]

        return leads

    def _append_lead_filters(self, query, params, status=None, job_id=None, has_email=None, has_website=None, has_phone=None, lead_flag=None, lead_status=None, business_type=None, search_location=None):
        if status:
            query += " AND l.status = ?"
            params.append(status)

        if job_id:
            query += """
                AND EXISTS (
                    SELECT 1
                    FROM lead_discoveries ld_job
                    JOIN job_executions j_job ON ld_job.execution_id = j_job.execution_id
                    WHERE ld_job.lead_id = l.lead_id
                      AND j_job.job_id = ?
                )
            """
            params.append(job_id)

        if lead_flag:
            query += " AND l.lead_flag = ?"
            params.append(lead_flag)

        if lead_status:
            query += " AND l.lead_status = ?"
            params.append(lead_status)

        if business_type:
            query += """
                AND EXISTS (
                    SELECT 1
                    FROM lead_discoveries ld_business
                    WHERE ld_business.lead_id = l.lead_id
                      AND (
                          ld_business.business_type = ?
                          OR ld_business.location LIKE ?
                      )
                )
            """
            params.extend([business_type, f"{business_type}:%"])

        if search_location:
            query += """
                AND EXISTS (
                    SELECT 1
                    FROM lead_discoveries ld_location
                    WHERE ld_location.lead_id = l.lead_id
                      AND (
                          ld_location.search_location = ?
                          OR ld_location.location = ?
                          OR ld_location.location LIKE ?
                      )
                )
            """
            params.extend([search_location, search_location, f"%:{search_location}"])

        if has_email is True:
            query += " AND l.emails IS NOT NULL AND TRIM(l.emails) != ''"
        elif has_email is False:
            query += " AND (l.emails IS NULL OR TRIM(l.emails) = '')"

        if has_website is True:
            query += " AND l.website IS NOT NULL AND TRIM(l.website) != ''"
        elif has_website is False:
            query += " AND (l.website IS NULL OR TRIM(l.website) = '')"

        if has_phone is True:
            query += " AND l.phone IS NOT NULL AND TRIM(l.phone) != ''"
        elif has_phone is False:
            query += " AND (l.phone IS NULL OR TRIM(l.phone) = '')"

        return query

    def list_leads(self, status=None, job_id=None, has_email=None, has_website=None, has_phone=None, lead_flag=None, lead_status=None, business_type=None, search_location=None):
        """Retrieves leads for UI listing with optional filters.

        Args:
            status (str, optional): Exact lead status to match.
            job_id (str, optional): Parent job UUID to match.
            has_email (bool, optional): If True, only leads with emails. If False,
                only leads without emails.
            has_website (bool, optional): If True, only leads with websites. If
                False, only leads without websites.

        Returns:
            list[dict]: Lead rows joined with their parent job metadata.
        """
        try:
            query = """
                SELECT
                    l.lead_id,
                    l.execution_id,
                    l.place_id,
                    l.location,
                    l.name,
                    l.address,
                    l.phone,
                    l.website,
                    l.emails,
                    l.status,
                    l.lead_flag,
                    l.lead_status,
                    l.notes,
                    l.website_summary,
                    l.summary_source_url,
                    l.summary_status,
                    l.summary_updated_at,
                    l.created_at,
                    l.updated_at,
                    j.job_id,
                    j.step_id,
                    j.status AS job_status,
                    (
                        SELECT COUNT(*)
                        FROM lead_discoveries ld_count
                        WHERE ld_count.lead_id = l.lead_id
                    ) AS discovery_count,
                    (
                        SELECT MAX(ld_last.updated_at)
                        FROM lead_discoveries ld_last
                        WHERE ld_last.lead_id = l.lead_id
                    ) AS last_discovered_at,
                    (
                        SELECT j_last.job_id
                        FROM lead_discoveries ld_last_job
                        JOIN job_executions j_last ON ld_last_job.execution_id = j_last.execution_id
                        WHERE ld_last_job.lead_id = l.lead_id
                        ORDER BY ld_last_job.updated_at DESC, ld_last_job.discovery_id DESC
                        LIMIT 1
                    ) AS last_discovery_job_id
                FROM leads l
                JOIN job_executions j ON l.execution_id = j.execution_id
                WHERE 1 = 1
            """
            params = []

            query = self._append_lead_filters(
                query,
                params,
                status=status,
                job_id=job_id,
                has_email=has_email,
                has_website=has_website,
                has_phone=has_phone,
                lead_flag=lead_flag,
                lead_status=lead_status,
                business_type=business_type,
                search_location=search_location,
            )

            query += " ORDER BY l.created_at DESC"

            self.cursor.execute(query, params)
            rows = self.cursor.fetchall()
            leads = [dict(row) for row in rows] if rows else []
            return self._attach_campaign_memberships(leads)
        except sqlite3.Error as e:
            logging.error(f"Failed to list leads: {e}")
            return []

    def _parse_campaign_source(self, filters, leads):
        """Derives business type and search location from explicit filters or lead.location."""
        business_type = (filters or {}).get("business_type")
        search_location = (filters or {}).get("search_location")

        if business_type or search_location:
            return business_type, search_location

        for lead in leads:
            location = lead.get("location")
            if isinstance(location, str) and ":" in location:
                parsed_business_type, parsed_location = location.split(":", 1)
                return parsed_business_type.strip() or None, parsed_location.strip() or None

        return None, None

    def list_lead_filter_options(self):
        """Returns distinct business type and search location values parsed from discoveries."""
        try:
            self.cursor.execute("""
                SELECT location, business_type, search_location
                FROM lead_discoveries
                WHERE (
                    location IS NOT NULL AND TRIM(location) != ''
                ) OR (
                    business_type IS NOT NULL AND TRIM(business_type) != ''
                ) OR (
                    search_location IS NOT NULL AND TRIM(search_location) != ''
                )
            """)
            business_type_counts = {}
            search_location_counts = {}
            pair_counts = {}

            for row in self.cursor.fetchall():
                business_type = row["business_type"]
                search_location = row["search_location"]
                location = row["location"]
                if self._is_blank(business_type) and self._is_blank(search_location):
                    business_type, search_location = self._split_lead_location(location)

                if business_type == "":
                    business_type = None
                if search_location == "":
                    search_location = None

                if business_type:
                    business_type_counts[business_type] = business_type_counts.get(business_type, 0) + 1
                if search_location:
                    search_location_counts[search_location] = search_location_counts.get(search_location, 0) + 1
                if business_type and search_location:
                    pair_key = (business_type, search_location)
                    pair_counts[pair_key] = pair_counts.get(pair_key, 0) + 1

            business_types = [
                {"value": value, "count": count}
                for value, count in business_type_counts.items()
            ]
            search_locations = [
                {"value": value, "count": count}
                for value, count in search_location_counts.items()
            ]
            pairs = [
                {
                    "business_type": business_type,
                    "search_location": search_location,
                    "count": count,
                }
                for (business_type, search_location), count in pair_counts.items()
            ]

            return {
                "business_types": sorted(business_types, key=lambda item: item["value"].lower()),
                "search_locations": sorted(search_locations, key=lambda item: item["value"].lower()),
                "pairs": sorted(
                    pairs,
                    key=lambda item: (item["business_type"].lower(), item["search_location"].lower()),
                ),
            }
        except sqlite3.Error as e:
            logging.error(f"Failed to list lead filter options: {e}")
            return {
                "business_types": [],
                "search_locations": [],
                "pairs": [],
            }

    def create_campaign(self, name, filters=None, notes=None):
        """Creates a campaign from current matching leads."""
        filters = filters or {}
        leads = self.list_leads(
            status=filters.get("status"),
            job_id=filters.get("job_id"),
            has_email=filters.get("has_email"),
            has_website=filters.get("has_website"),
            has_phone=filters.get("has_phone"),
            lead_flag=filters.get("lead_flag"),
            lead_status=filters.get("lead_status"),
            business_type=filters.get("business_type"),
            search_location=filters.get("search_location"),
        )
        business_type, search_location = self._parse_campaign_source(filters, leads)

        self.cursor.execute("""
            INSERT INTO campaigns (
                name, business_type, search_location, filters_json, status, notes, updated_at
            ) VALUES (?, ?, ?, ?, 'draft', ?, CURRENT_TIMESTAMP)
        """, (name, business_type, search_location, json.dumps(filters), notes))
        campaign_id = self.cursor.lastrowid

        added = 0
        skipped_existing = 0
        for lead in leads:
            try:
                self.cursor.execute("""
                    INSERT INTO campaign_leads (campaign_id, lead_id, stage, updated_at)
                    VALUES (?, ?, 'review', CURRENT_TIMESTAMP)
                """, (campaign_id, lead["lead_id"]))
                added += 1
            except sqlite3.IntegrityError:
                skipped_existing += 1

        campaign = self.get_campaign(campaign_id)
        return {
            "campaign": campaign,
            "added_leads": added,
            "skipped_existing": skipped_existing,
        }

    def list_campaigns(self):
        """Lists campaigns with stage summary counts."""
        self.cursor.execute("""
            SELECT
                c.campaign_id,
                c.name,
                c.business_type,
                c.search_location,
                c.filters_json,
                c.status,
                c.notes,
                c.created_at,
                c.updated_at,
                COUNT(cl.campaign_lead_id) AS total_leads,
                SUM(CASE WHEN cl.stage = 'review' THEN 1 ELSE 0 END) AS review,
                SUM(CASE WHEN cl.stage = 'ready_for_email' THEN 1 ELSE 0 END) AS ready_for_email,
                SUM(CASE WHEN cl.stage = 'drafted' THEN 1 ELSE 0 END) AS drafted,
                SUM(CASE WHEN cl.stage = 'approved' THEN 1 ELSE 0 END) AS approved,
                SUM(CASE WHEN cl.stage = 'contacted' THEN 1 ELSE 0 END) AS contacted,
                SUM(CASE WHEN cl.stage = 'replied' THEN 1 ELSE 0 END) AS replied,
                SUM(CASE WHEN cl.stage = 'closed' THEN 1 ELSE 0 END) AS closed,
                SUM(CASE WHEN cl.stage = 'skipped' THEN 1 ELSE 0 END) AS skipped,
                SUM(CASE WHEN cl.stage = 'do_not_contact' THEN 1 ELSE 0 END) AS do_not_contact
            FROM campaigns c
            LEFT JOIN campaign_leads cl ON c.campaign_id = cl.campaign_id
            GROUP BY c.campaign_id
            ORDER BY c.updated_at DESC, c.campaign_id DESC
        """)
        rows = self.cursor.fetchall()
        campaigns = [dict(row) for row in rows] if rows else []
        for campaign in campaigns:
            for key in ["total_leads", "review", "ready_for_email", "drafted", "approved", "contacted", "replied", "closed", "skipped", "do_not_contact"]:
                campaign[key] = campaign.get(key) or 0
        return campaigns

    def get_campaign(self, campaign_id):
        """Gets a campaign with summary counts."""
        campaigns = self.list_campaigns()
        return next((campaign for campaign in campaigns if campaign["campaign_id"] == campaign_id), None)

    def update_campaign(self, campaign_id, name=None, status=None, notes=None):
        """Updates campaign fields."""
        set_clauses = []
        params = []
        if name is not None:
            set_clauses.append("name = ?")
            params.append(name)
        if status is not None:
            set_clauses.append("status = ?")
            params.append(status)
        if notes is not None:
            set_clauses.append("notes = ?")
            params.append(notes)

        if set_clauses:
            set_clauses.append("updated_at = CURRENT_TIMESTAMP")
            params.append(campaign_id)
            self.cursor.execute(
                f"UPDATE campaigns SET {', '.join(set_clauses)} WHERE campaign_id = ?",
                params,
            )
            if self.cursor.rowcount == 0:
                return None

        return self.get_campaign(campaign_id)

    def list_campaign_leads(self, campaign_id, stage=None, lead_flag=None, lead_status=None, has_email=None, has_website=None, search=None):
        """Lists campaign leads joined to base lead data."""
        query = """
            SELECT
                cl.*,
                l.execution_id,
                l.place_id,
                l.location,
                l.name,
                l.address,
                l.phone,
                l.website,
                l.emails,
                l.status AS lead_scrape_status,
                l.lead_flag,
                l.lead_status,
                l.notes,
                l.website_summary,
                l.summary_source_url,
                l.summary_status,
                l.summary_updated_at,
                l.created_at AS lead_created_at,
                l.updated_at AS lead_updated_at,
                j.job_id,
                c.name AS campaign_name,
                c.business_type,
                c.search_location,
                (
                    SELECT le.email
                    FROM lead_emails le
                    WHERE le.lead_id = l.lead_id
                      AND le.status NOT IN ('invalid', 'do_not_use')
                    ORDER BY le.is_primary DESC, le.email_id ASC
                    LIMIT 1
                ) AS primary_email
            FROM campaign_leads cl
            JOIN campaigns c ON cl.campaign_id = c.campaign_id
            JOIN leads l ON cl.lead_id = l.lead_id
            JOIN job_executions j ON l.execution_id = j.execution_id
            WHERE cl.campaign_id = ?
        """
        params = [campaign_id]

        if stage:
            query += " AND cl.stage = ?"
            params.append(stage)
        if lead_flag:
            query += " AND l.lead_flag = ?"
            params.append(lead_flag)
        if lead_status:
            query += " AND l.lead_status = ?"
            params.append(lead_status)
        if has_email is True:
            query += " AND l.emails IS NOT NULL AND TRIM(l.emails) != ''"
        elif has_email is False:
            query += " AND (l.emails IS NULL OR TRIM(l.emails) = '')"
        if has_website is True:
            query += " AND l.website IS NOT NULL AND TRIM(l.website) != ''"
        elif has_website is False:
            query += " AND (l.website IS NULL OR TRIM(l.website) = '')"
        if search:
            query += " AND (l.name LIKE ? OR l.address LIKE ? OR l.emails LIKE ?)"
            token = f"%{search}%"
            params.extend([token, token, token])

        query += " ORDER BY cl.updated_at DESC, cl.campaign_lead_id DESC"
        self.cursor.execute(query, params)
        rows = self.cursor.fetchall()
        return [dict(row) for row in rows] if rows else []

    def update_campaign_lead(self, campaign_lead_id, stage=None, priority=None, email_draft=None, final_email=None, campaign_notes=None, contacted_at=None):
        """Updates campaign-lead workflow fields."""
        set_clauses = []
        params = []
        for column, value in {
            "stage": stage,
            "priority": priority,
            "email_draft": email_draft,
            "final_email": final_email,
            "campaign_notes": campaign_notes,
            "contacted_at": contacted_at,
        }.items():
            if value is not None:
                set_clauses.append(f"{column} = ?")
                params.append(value)

        if set_clauses:
            set_clauses.append("updated_at = CURRENT_TIMESTAMP")
            params.append(campaign_lead_id)
            self.cursor.execute(
                f"UPDATE campaign_leads SET {', '.join(set_clauses)} WHERE campaign_lead_id = ?",
                params,
            )
            if self.cursor.rowcount == 0:
                return None

        self.cursor.execute("SELECT campaign_id FROM campaign_leads WHERE campaign_lead_id = ?", (campaign_lead_id,))
        row = self.cursor.fetchone()
        if not row:
            return None
        self.cursor.execute(
            "UPDATE campaigns SET updated_at = CURRENT_TIMESTAMP WHERE campaign_id = ?",
            (row["campaign_id"],),
        )
        leads = self.list_campaign_leads(row["campaign_id"])
        return next((lead for lead in leads if lead["campaign_lead_id"] == campaign_lead_id), None)

    def get_campaign_lead(self, campaign_lead_id):
        """Gets one campaign lead joined to campaign and base lead context."""
        self.cursor.execute("SELECT campaign_id FROM campaign_leads WHERE campaign_lead_id = ?", (campaign_lead_id,))
        row = self.cursor.fetchone()
        if not row:
            return None
        leads = self.list_campaign_leads(row["campaign_id"])
        return next((lead for lead in leads if lead["campaign_lead_id"] == campaign_lead_id), None)

    def get_email_settings(self):
        """Returns AI email settings without exposing provider API keys."""
        self.cursor.execute("SELECT key, value FROM app_settings")
        rows = self.cursor.fetchall()
        settings = dict(DEFAULT_EMAIL_SETTINGS)
        settings.update({row["key"]: row["value"] for row in rows})

        provider = settings.get("ai_email_provider") or DEFAULT_EMAIL_SETTINGS["ai_email_provider"]
        return {
            "provider": provider,
            "model": settings.get("ai_email_model") or DEFAULT_EMAIL_SETTINGS["ai_email_model"],
            "system_prompt": settings.get("ai_email_system_prompt") or DEFAULT_EMAIL_SYSTEM_PROMPT,
            "user_prompt": settings.get("ai_email_user_prompt") or DEFAULT_EMAIL_USER_PROMPT,
            "api_key_configured": self._is_ai_provider_key_configured(provider),
        }

    def update_email_settings(self, provider=None, model=None, system_prompt=None, user_prompt=None):
        """Updates AI email settings."""
        updates = {}
        if provider is not None:
            updates["ai_email_provider"] = provider
        if model is not None:
            updates["ai_email_model"] = model
        if system_prompt is not None:
            updates["ai_email_system_prompt"] = system_prompt
        if user_prompt is not None:
            updates["ai_email_user_prompt"] = user_prompt

        for key, value in updates.items():
            self.cursor.execute("""
                INSERT INTO app_settings (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = CURRENT_TIMESTAMP
            """, (key, value))
        return self.get_email_settings()

    def _is_ai_provider_key_configured(self, provider):
        if provider == "openai":
            return bool(Config.OPENAI_API_KEY)
        if provider == "anthropic":
            return bool(Config.ANTHROPIC_API_KEY)
        return False

    def list_business_type_email_rules(self):
        """Lists configured email personalization rules by business type."""
        self.cursor.execute("""
            SELECT business_type, business_description, pain_point, offer_angle,
                   extra_instructions, created_at, updated_at
            FROM business_type_email_rules
            ORDER BY business_type COLLATE NOCASE
        """)
        rows = self.cursor.fetchall()
        return [dict(row) for row in rows] if rows else []

    def get_business_type_email_rule(self, business_type):
        """Gets one business-type email rule."""
        self.cursor.execute("""
            SELECT business_type, business_description, pain_point, offer_angle,
                   extra_instructions, created_at, updated_at
            FROM business_type_email_rules
            WHERE business_type = ?
        """, (business_type,))
        row = self.cursor.fetchone()
        return dict(row) if row else None

    def upsert_business_type_email_rule(self, business_type, business_description=None, pain_point=None, offer_angle=None, extra_instructions=None):
        """Creates or updates a business-type email personalization rule."""
        self.cursor.execute("""
            INSERT INTO business_type_email_rules (
                business_type, business_description, pain_point, offer_angle,
                extra_instructions, updated_at
            ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(business_type) DO UPDATE SET
                business_description = excluded.business_description,
                pain_point = excluded.pain_point,
                offer_angle = excluded.offer_angle,
                extra_instructions = excluded.extra_instructions,
                updated_at = CURRENT_TIMESTAMP
        """, (business_type, business_description, pain_point, offer_angle, extra_instructions))
        return self.get_business_type_email_rule(business_type)

    def store_generated_email_draft(self, campaign_lead_id, email_draft):
        """Stores an AI-generated draft without overwriting the final email."""
        lead = self.get_campaign_lead(campaign_lead_id)
        if not lead:
            return None

        blocked_stages = {"approved", "contacted", "replied", "closed", "skipped", "do_not_contact"}
        next_stage = lead.get("stage") if lead.get("stage") in blocked_stages else "drafted"
        return self.update_campaign_lead(
            campaign_lead_id=campaign_lead_id,
            email_draft=email_draft,
            stage=next_stage,
        )

    def _normalize_email_rule_pattern(self, pattern):
        return str(pattern or "").strip().lower()

    def list_email_category_rules(self):
        """Lists local-part email category rules."""
        self.cursor.execute("""
            SELECT rule_id, pattern, match_type, category, is_active, created_at, updated_at
            FROM email_category_rules
            ORDER BY pattern COLLATE NOCASE
        """)
        rows = self.cursor.fetchall()
        return [dict(row) for row in rows] if rows else []

    def get_email_category_rule(self, pattern, match_type="local_part_exact"):
        """Gets one email category rule."""
        normalized_pattern = self._normalize_email_rule_pattern(pattern)
        self.cursor.execute("""
            SELECT rule_id, pattern, match_type, category, is_active, created_at, updated_at
            FROM email_category_rules
            WHERE pattern = ? AND match_type = ?
        """, (normalized_pattern, match_type))
        row = self.cursor.fetchone()
        return dict(row) if row else None

    def upsert_email_category_rule(self, pattern, category, match_type="local_part_exact", is_active=True):
        """Creates or updates a local-part email category rule."""
        normalized_pattern = self._normalize_email_rule_pattern(pattern)
        if not normalized_pattern:
            raise ValueError("pattern is required")
        if match_type != "local_part_exact":
            raise ValueError("Only local_part_exact rules are supported")
        if category not in EMAIL_CATEGORY_VALUES or category == "unknown":
            raise ValueError("category must be a known non-unknown category")

        self.cursor.execute("""
            INSERT INTO email_category_rules (
                pattern, match_type, category, is_active, updated_at
            ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(pattern, match_type) DO UPDATE SET
                category = excluded.category,
                is_active = excluded.is_active,
                updated_at = CURRENT_TIMESTAMP
        """, (normalized_pattern, match_type, category, bool(is_active)))
        return self.get_email_category_rule(normalized_pattern, match_type)

    def list_unknown_email_local_parts(self):
        """Lists unknown email local-parts with examples and counts."""
        self.cursor.execute("""
            SELECT
                LOWER(SUBSTR(email, 1, INSTR(email, '@') - 1)) AS local_part,
                COUNT(*) AS count,
                MIN(email) AS example_email
            FROM lead_emails
            WHERE category = 'unknown'
              AND email IS NOT NULL
              AND INSTR(email, '@') > 1
            GROUP BY LOWER(SUBSTR(email, 1, INSTR(email, '@') - 1))
            ORDER BY count DESC, local_part COLLATE NOCASE
        """)
        rows = self.cursor.fetchall()
        return [dict(row) for row in rows] if rows else []

    def apply_email_category_rules_to_unknowns(self):
        """Applies active rules to currently unknown email rows only."""
        self.cursor.execute("""
            UPDATE lead_emails
            SET category = (
                SELECT category
                FROM email_category_rules
                WHERE is_active = TRUE
                  AND match_type = 'local_part_exact'
                  AND pattern = LOWER(SUBSTR(lead_emails.email, 1, INSTR(lead_emails.email, '@') - 1))
                LIMIT 1
            ),
            updated_at = CURRENT_TIMESTAMP
            WHERE category = 'unknown'
              AND EXISTS (
                SELECT 1
                FROM email_category_rules
                WHERE is_active = TRUE
                  AND match_type = 'local_part_exact'
                  AND pattern = LOWER(SUBSTR(lead_emails.email, 1, INSTR(lead_emails.email, '@') - 1))
              )
        """)
        updated_count = self.cursor.rowcount
        return {
            "updated_count": updated_count,
            "unknown_local_parts": self.list_unknown_email_local_parts(),
        }

    def insert_lead(self, execution_id, place_id, location=None, name=None, address=None, phone=None, website=None, emails=None):
        """Inserts a new lead record into the database.

        Note: This method will fail if a lead with the same place_id already
        exists, due to global lead uniqueness. Use `update_lead` for modifying
        existing records.

        Args:
            execution_id (int): The identifier of the job execution that generated this lead.
            place_id (str): The unique identifier for the place (e.g., from Google Maps).
            location (str, optional): The location searched. Defaults to None.
            name (str, optional): The name of the business. Defaults to None.
            address (str, optional): The address of the business. Defaults to None.
            phone (str, optional): The phone number. Defaults to None.
            website (str, optional): The business's website. Defaults to None.
            emails (str, optional): A comma-separated string of found emails. Defaults to None.
        """
        try:
            self.cursor.execute("""
                INSERT INTO leads (
                    execution_id, place_id, location, name, address, phone, website, emails, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (execution_id, place_id, location, name, address, phone, website, emails))
            lead_id = self.cursor.lastrowid
            self._record_lead_discovery_with_cursor(self.cursor, lead_id, execution_id, place_id, location)
            if emails:
                self._backfill_lead_emails_from_string(lead_id, emails)
            logging.info(f"Inserted lead for execution {execution_id}, place {place_id}")
        except sqlite3.Error as e:
            logging.error(f"Failed to insert lead for execution {execution_id}, place {place_id}: {e}")
            raise

    def get_lead_by_place_id(self, place_id):
        """Returns one canonical lead by Google Places place_id."""
        self.cursor.execute("""
            SELECT *
            FROM leads
            WHERE place_id = ?
        """, (place_id,))
        row = self.cursor.fetchone()
        return dict(row) if row else None

    def record_lead_discovery(self, lead_id, execution_id, place_id, location=None):
        """Records that a scrape job found an existing canonical lead."""
        self._record_lead_discovery_with_cursor(self.cursor, lead_id, execution_id, place_id, location)

    def upsert_google_places_lead(self, execution_id, place_id, location=None, name=None, address=None, phone=None, website=None):
        """Creates or refreshes a canonical Google Places lead and records discovery.

        Google-owned fields are refreshed only when the new value is non-empty.
        Manual/enrichment fields such as emails, review status, notes, campaigns,
        and website summaries are not overwritten here.
        """
        existing = self.get_lead_by_place_id(place_id)
        if not existing:
            self.insert_lead(
                execution_id=execution_id,
                place_id=place_id,
                location=location,
                name=name,
                address=address,
                phone=phone,
                website=website,
            )
            lead = self.get_lead_by_place_id(place_id)
            if lead:
                lead["storage_status"] = "created"
            return lead

        set_clauses = []
        params = []
        for column, value in {
            "location": location,
            "name": name,
            "address": address,
            "phone": phone,
            "website": website,
        }.items():
            if not self._is_blank(value):
                set_clauses.append(f"{column} = ?")
                params.append(value)

        if set_clauses:
            set_clauses.append("updated_at = CURRENT_TIMESTAMP")
            params.append(existing["lead_id"])
            self.cursor.execute(
                f"UPDATE leads SET {', '.join(set_clauses)} WHERE lead_id = ?",
                params,
            )

        self.record_lead_discovery(existing["lead_id"], execution_id, place_id, location)
        lead = self.get_lead_by_place_id(place_id)
        if lead:
            lead["storage_status"] = "updated"
        return lead

    def update_lead(self, place_id, execution_id=None, location=None, name=None, address=None, phone=None, website=None, emails=None, status=None, website_summary=None, summary_source_url=None, summary_status=None):
        """Updates an existing lead record in the database.

        Args:
            place_id (str): The unique identifier of the place to update.
            execution_id (int, optional): The identifier of the job execution. Defaults to None.
            location (str, optional): The new location. Defaults to None.
            name (str, optional): The new name. Defaults to None.
            address (str, optional): The new address. Defaults to None.
            phone (str, optional): The new phone number. Defaults to None.
            website (str, optional): The new website. Defaults to None.
            emails (str, optional): The new comma-separated email string. Defaults to None.
            status (str, optional): The new status of the lead. Defaults to None.
            website_summary (str, optional): Cleaned public website context text.
            summary_source_url (str, optional): Page URL used for the summary.
            summary_status (str, optional): Summary capture status.
        """
        try:
            set_clauses = []
            params = []
            if location is not None:
                set_clauses.append("location = ?")
                params.append(location)
            if name is not None:
                set_clauses.append("name = ?")
                params.append(name)
            if address is not None:
                set_clauses.append("address = ?")
                params.append(address)
            if phone is not None:
                set_clauses.append("phone = ?")
                params.append(phone)
            if website is not None:
                set_clauses.append("website = ?")
                params.append(website)
            if emails is not None:
                set_clauses.append("emails = ?")
                params.append(emails)
            if status is not None:
                set_clauses.append("status = ?")
                params.append(status)
            summary_fields_changed = any(value is not None for value in [website_summary, summary_source_url, summary_status])
            if website_summary is not None:
                set_clauses.append("website_summary = ?")
                params.append(website_summary)
            if summary_source_url is not None:
                set_clauses.append("summary_source_url = ?")
                params.append(summary_source_url)
            if summary_status is not None:
                set_clauses.append("summary_status = ?")
                params.append(summary_status)
            if summary_fields_changed:
                set_clauses.append("summary_updated_at = CURRENT_TIMESTAMP")
            set_clauses.append("updated_at = CURRENT_TIMESTAMP")

            if not set_clauses:
                logging.warning(f"No fields to update for lead with place {place_id}")
                return

            query = f"UPDATE leads SET {', '.join(set_clauses)} WHERE place_id = ?"
            params.extend([place_id])
            
            # If execution_id is provided, add it to the WHERE clause for more specific targeting
            if execution_id is not None:
                query += " AND execution_id = ?"
                params.append(execution_id)

            self.cursor.execute(query, params)
            if self.cursor.rowcount == 0:
                logging.warning(f"No record found to update for lead with place {place_id}")
            else:
                if emails is not None:
                    lookup_query = "SELECT lead_id FROM leads WHERE place_id = ?"
                    lookup_params = [place_id]
                    if execution_id is not None:
                        lookup_query += " AND execution_id = ?"
                        lookup_params.append(execution_id)
                    self.cursor.execute(lookup_query, lookup_params)
                    lead_row = self.cursor.fetchone()
                    if lead_row:
                        self._backfill_lead_emails_from_string(lead_row["lead_id"], emails)
                logging.info(f"Updated lead for place {place_id}")
        except sqlite3.Error as e:
            logging.error(f"Failed to update lead for place {place_id}: {e}")
            raise

    def _backfill_lead_emails_from_string(self, lead_id, emails):
        """Adds comma-separated legacy emails into normalized lead_emails."""
        parsed_emails = [
            email.strip()
            for email in str(emails or "").split(",")
            if email.strip()
        ]
        for index, email in enumerate(parsed_emails):
            self.cursor.execute("""
                INSERT OR IGNORE INTO lead_emails (
                    lead_id, email, category, status, is_primary
                ) VALUES (?, ?, 'unknown', 'new', ?)
            """, (lead_id, email, index == 0))

    def update_lead_by_id(self, lead_id, website=None, emails=None, status=None, lead_flag=None, lead_status=None, notes=None, website_summary=None):
        """Updates editable lead fields by lead_id.

        Args:
            lead_id (int): The primary key of the lead to update.
            website (str | None): Replacement website value.
            emails (str | None): Replacement comma-separated emails value.
            status (str | None): Replacement lead status.
            website_summary (str | None): Replacement website context text.

        Returns:
            dict | None: The updated lead row, or None if no row was found.
        """
        try:
            set_clauses = []
            params = []

            if website is not None:
                set_clauses.append("website = ?")
                params.append(website)
            if emails is not None:
                set_clauses.append("emails = ?")
                params.append(emails)
            if status is not None:
                set_clauses.append("status = ?")
                params.append(status)
            if lead_flag is not None:
                set_clauses.append("lead_flag = ?")
                params.append(lead_flag)
            if lead_status is not None:
                set_clauses.append("lead_status = ?")
                params.append(lead_status)
            if notes is not None:
                set_clauses.append("notes = ?")
                params.append(notes)
            if website_summary is not None:
                set_clauses.append("website_summary = ?")
                params.append(website_summary)
                set_clauses.append("summary_updated_at = CURRENT_TIMESTAMP")

            if not set_clauses:
                self.cursor.execute("""
                    SELECT l.*, j.job_id, j.step_id, j.status AS job_status
                    FROM leads l
                    JOIN job_executions j ON l.execution_id = j.execution_id
                    WHERE l.lead_id = ?
                """, (lead_id,))
                row = self.cursor.fetchone()
                leads = self._attach_campaign_memberships([dict(row)]) if row else []
                return leads[0] if leads else None

            set_clauses.append("updated_at = CURRENT_TIMESTAMP")
            params.append(lead_id)

            self.cursor.execute(
                f"UPDATE leads SET {', '.join(set_clauses)} WHERE lead_id = ?",
                params
            )

            if self.cursor.rowcount == 0:
                return None

            if emails is not None:
                self._backfill_lead_emails_from_string(lead_id, emails)

            self.cursor.execute("""
                SELECT l.*, j.job_id, j.step_id, j.status AS job_status
                FROM leads l
                JOIN job_executions j ON l.execution_id = j.execution_id
                WHERE l.lead_id = ?
            """, (lead_id,))
            row = self.cursor.fetchone()
            leads = self._attach_campaign_memberships([dict(row)]) if row else []
            return leads[0] if leads else None
        except sqlite3.Error as e:
            logging.error(f"Failed to update lead {lead_id}: {e}")
            raise

    def _sync_lead_emails_string(self, lead_id):
        """Syncs legacy leads.emails from usable normalized email rows."""
        self.cursor.execute("""
            SELECT email
            FROM lead_emails
            WHERE lead_id = ?
              AND status NOT IN ('invalid', 'do_not_use')
            ORDER BY is_primary DESC, email_id ASC
        """, (lead_id,))
        emails = [row["email"] for row in self.cursor.fetchall()]
        emails_str = ",".join(emails) if emails else None
        self.cursor.execute("""
            UPDATE leads
            SET emails = ?, updated_at = CURRENT_TIMESTAMP
            WHERE lead_id = ?
        """, (emails_str, lead_id))

    def list_lead_emails(self, lead_id):
        """Lists normalized email rows for a lead."""
        try:
            self.cursor.execute("""
                SELECT *
                FROM lead_emails
                WHERE lead_id = ?
                ORDER BY is_primary DESC, email_id ASC
            """, (lead_id,))
            rows = self.cursor.fetchall()
            return [dict(row) for row in rows] if rows else []
        except sqlite3.Error as e:
            logging.error(f"Failed to list emails for lead {lead_id}: {e}")
            return []

    def add_lead_email(self, lead_id, email, category="unknown", status="new", is_primary=False, notes=None):
        """Adds an email to a lead and syncs the legacy emails field."""
        try:
            self.cursor.execute("SELECT lead_id FROM leads WHERE lead_id = ?", (lead_id,))
            if not self.cursor.fetchone():
                return None

            if is_primary:
                self.cursor.execute("UPDATE lead_emails SET is_primary = FALSE WHERE lead_id = ?", (lead_id,))

            self.cursor.execute("""
                INSERT INTO lead_emails (
                    lead_id, email, category, status, is_primary, notes
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(lead_id, email) DO UPDATE SET
                    category = excluded.category,
                    status = excluded.status,
                    is_primary = excluded.is_primary,
                    notes = excluded.notes,
                    updated_at = CURRENT_TIMESTAMP
            """, (lead_id, email, category, status, is_primary, notes))

            if is_primary:
                self.cursor.execute("""
                    UPDATE lead_emails
                    SET is_primary = FALSE
                    WHERE lead_id = ? AND email != ?
                """, (lead_id, email))

            self._sync_lead_emails_string(lead_id)
            self.cursor.execute("""
                SELECT *
                FROM lead_emails
                WHERE lead_id = ? AND email = ?
            """, (lead_id, email))
            row = self.cursor.fetchone()
            return dict(row) if row else None
        except sqlite3.Error as e:
            logging.error(f"Failed to add email for lead {lead_id}: {e}")
            raise

    def update_lead_email(self, email_id, category=None, status=None, is_primary=None, notes=None):
        """Updates a normalized email row."""
        try:
            self.cursor.execute("SELECT * FROM lead_emails WHERE email_id = ?", (email_id,))
            existing = self.cursor.fetchone()
            if not existing:
                return None

            lead_id = existing["lead_id"]
            if is_primary is True:
                self.cursor.execute("UPDATE lead_emails SET is_primary = FALSE WHERE lead_id = ?", (lead_id,))

            set_clauses = []
            params = []
            if category is not None:
                set_clauses.append("category = ?")
                params.append(category)
            if status is not None:
                set_clauses.append("status = ?")
                params.append(status)
            if is_primary is not None:
                set_clauses.append("is_primary = ?")
                params.append(is_primary)
            if notes is not None:
                set_clauses.append("notes = ?")
                params.append(notes)

            if set_clauses:
                set_clauses.append("updated_at = CURRENT_TIMESTAMP")
                params.append(email_id)
                self.cursor.execute(
                    f"UPDATE lead_emails SET {', '.join(set_clauses)} WHERE email_id = ?",
                    params
                )

            self._sync_lead_emails_string(lead_id)
            self.cursor.execute("SELECT * FROM lead_emails WHERE email_id = ?", (email_id,))
            row = self.cursor.fetchone()
            return dict(row) if row else None
        except sqlite3.Error as e:
            logging.error(f"Failed to update email {email_id}: {e}")
            raise

    def delete_lead_email(self, email_id):
        """Deletes a normalized email row and syncs the legacy emails field."""
        try:
            self.cursor.execute("SELECT lead_id FROM lead_emails WHERE email_id = ?", (email_id,))
            row = self.cursor.fetchone()
            if not row:
                return None

            lead_id = row["lead_id"]
            self.cursor.execute("DELETE FROM lead_emails WHERE email_id = ?", (email_id,))
            self._sync_lead_emails_string(lead_id)
            return {"email_id": email_id, "lead_id": lead_id}
        except sqlite3.Error as e:
            logging.error(f"Failed to delete email {email_id}: {e}")
            raise

    def get_export_leads(self):
        """Retrieves fully scraped leads that have at least a phone number or email.

        Returns:
            list[dict]: Leads with status='scraped' and at least one contact method.
        """
        try:
            self.cursor.execute("""
                SELECT l.lead_id, l.location, l.name, l.address, l.phone,
                       l.website, l.emails, l.status, l.created_at
                FROM leads l
                WHERE l.status = 'scraped'
                  AND (
                      (l.phone IS NOT NULL AND TRIM(l.phone) != '')
                      OR
                      (l.emails IS NOT NULL AND TRIM(l.emails) != '')
                  )
                ORDER BY l.created_at DESC
            """)
            rows = self.cursor.fetchall()
            return [dict(row) for row in rows] if rows else []
        except sqlite3.Error as e:
            logging.error(f"Failed to fetch export leads: {e}")
            return []

if __name__ == "__main__":
    with Database().initialize() as db:
        leads = db.get_leads()
        if leads and len(leads) > 300:
            print(leads[300])
