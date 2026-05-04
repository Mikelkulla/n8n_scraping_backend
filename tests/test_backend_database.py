import sys
import os
import pytest
import sqlite3
from unittest.mock import patch, MagicMock

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.database import Database
from backend.app_settings import Config

@pytest.fixture
def db():
    """Fixture to create an in-memory database for each test."""
    # Use :memory: for a clean, fast, in-memory database for each test
    database = Database(db_path=':memory:').initialize()
    yield database

@pytest.fixture
def temp_db(tmp_path):
    """Fixture to create a database in a temporary file."""
    db_path = tmp_path / "test.db"
    database = Database(db_path=str(db_path)).initialize()
    yield database, str(db_path)

class TestDatabase:
    def test_constructor_does_not_create_database_file(self, tmp_path):
        """Test that construction does not run schema initialization."""
        db_path = tmp_path / "lazy.db"
        database = Database(db_path=str(db_path))

        assert database.db_path == str(db_path)
        assert not db_path.exists()

    def test_init_db_with_path(self, temp_db):
        """Test that the database is created at the specified file path."""
        _, db_path = temp_db
        assert os.path.exists(db_path)

    def test_init_db_creates_tables(self, temp_db):
        """Test that the tables are created with the correct columns."""
        db, _ = temp_db
        with db as conn:
            cursor = conn.cursor
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            assert 'job_executions' in tables
            assert 'leads' in tables
            assert 'lead_discoveries' in tables
            assert 'campaigns' in tables
            assert 'campaign_leads' in tables

            cursor.execute("PRAGMA table_info(job_executions);")
            job_columns = [row[1] for row in cursor.fetchall()]
            assert 'job_id' in job_columns
            assert 'step_id' in job_columns
            assert 'status' in job_columns

            cursor.execute("PRAGMA table_info(leads);")
            lead_columns = [row[1] for row in cursor.fetchall()]
            assert 'lead_id' in lead_columns
            assert 'execution_id' in lead_columns
            assert 'place_id' in lead_columns
            assert 'website_summary' in lead_columns
            assert 'summary_source_url' in lead_columns
            assert 'summary_status' in lead_columns
            assert 'summary_updated_at' in lead_columns

            cursor.execute("PRAGMA table_info(campaigns);")
            campaign_columns = [row[1] for row in cursor.fetchall()]
            assert 'campaign_id' in campaign_columns
            assert 'filters_json' in campaign_columns

            cursor.execute("PRAGMA table_info(campaign_leads);")
            campaign_lead_columns = [row[1] for row in cursor.fetchall()]
            assert 'campaign_lead_id' in campaign_lead_columns
            assert 'stage' in campaign_lead_columns

            cursor.execute("PRAGMA table_info(lead_discoveries);")
            discovery_columns = [row[1] for row in cursor.fetchall()]
            assert 'lead_id' in discovery_columns
            assert 'execution_id' in discovery_columns
            assert 'business_type' in discovery_columns
            assert 'search_location' in discovery_columns

    def test_init_db_adds_summary_columns_to_existing_leads_table(self, tmp_path):
        """Test that initialization migrates existing databases with summary columns."""
        db_path = tmp_path / "existing.db"
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE job_executions (
                execution_id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                step_id TEXT NOT NULL,
                input TEXT NOT NULL,
                status TEXT NOT NULL,
                UNIQUE(job_id, step_id)
            )
        """)
        conn.execute("""
            CREATE TABLE leads (
                lead_id INTEGER PRIMARY KEY AUTOINCREMENT,
                execution_id INTEGER NOT NULL,
                place_id TEXT NOT NULL,
                website TEXT,
                emails TEXT,
                status TEXT
            )
        """)
        conn.commit()
        conn.close()

        Database(db_path=str(db_path)).initialize()

        migrated = sqlite3.connect(db_path)
        cursor = migrated.cursor()
        cursor.execute("PRAGMA table_info(leads);")
        lead_columns = [row[1] for row in cursor.fetchall()]
        migrated.close()

        assert "website_summary" in lead_columns
        assert "summary_source_url" in lead_columns
        assert "summary_status" in lead_columns
        assert "summary_updated_at" in lead_columns

    def test_insert_and_get_job_execution(self, temp_db):
        """Test inserting and retrieving a job execution."""
        db, _ = temp_db
        with db as conn:
            conn.insert_job_execution(
                job_id="job1",
                step_id="step1",
                input="test_input",
                status="running"
            )
            job = conn.get_job_execution("job1", "step1")
            assert job is not None
            assert job['job_id'] == "job1"
            assert job['status'] == "running"

    def test_get_nonexistent_job_execution(self, temp_db):
        """Test that get_job_execution returns None for a non-existent job."""
        db, _ = temp_db
        with db as conn:
            job = conn.get_job_execution("job_unknown", "step_unknown")
            assert job is None

    def test_insert_job_execution_uniqueness(self, temp_db):
        """Test that inserting a job with a duplicate (job_id, step_id) fails."""
        db, _ = temp_db
        with db as conn:
            conn.insert_job_execution("job1", "step1", "input1", status="running")
            with pytest.raises(sqlite3.IntegrityError):
                conn.insert_job_execution("job1", "step1", "input1", status="completed")

    def test_update_job_execution(self, temp_db):
        """Test updating various fields of a job execution."""
        db, _ = temp_db
        with db as conn:
            conn.insert_job_execution("job1", "step1", "input1", status="running", current_row=10, total_rows=100)
            conn.update_job_execution(
                job_id="job1",
                step_id="step1",
                status="completed",
                current_row=100,
                error_message="All good"
            )
            job = conn.get_job_execution("job1", "step1")
            assert job['status'] == "completed"
            assert job['current_row'] == 100
            assert job['error_message'] == "All good"

    def test_update_job_execution_selective(self, temp_db):
        """Test that only specified fields are updated."""
        db, _ = temp_db
        with db as conn:
            conn.insert_job_execution("job1", "step1", "input1", status="running", current_row=10)
            conn.update_job_execution(job_id="job1", step_id="step1", status="paused")
            job = conn.get_job_execution("job1", "step1")
            assert job['status'] == "paused"
            assert job['current_row'] == 10  # Should be unchanged

    @patch('logging.warning')
    def test_update_nonexistent_job_execution(self, mock_warning, temp_db):
        """Test updating a non-existent job execution."""
        db, _ = temp_db
        with db as conn:
            conn.update_job_execution(job_id="job_unknown", step_id="step_unknown", status="failed")
            mock_warning.assert_called_once()
            assert "No record found to update" in mock_warning.call_args[0][0]

    def test_insert_and_get_lead(self, temp_db):
        """Test inserting and retrieving a lead."""
        db, _ = temp_db
        with db as conn:
            # First, insert a job execution for the foreign key constraint
            conn.insert_job_execution("job1", "step1", "input1", status="running")
            execution = conn.get_job_execution("job1", "step1")
            execution_id = execution['execution_id']

            conn.insert_lead(
                execution_id=execution_id,
                place_id="place1",
                name="Test Business",
                website="http://example.com"
            )
            leads = conn.get_leads()
            assert len(leads) == 1
            assert leads[0]['name'] == "Test Business"
            assert leads[0]['job_id'] == "job1" # Test the join

    def test_get_leads_empty(self, temp_db):
        """Test retrieving leads when the table is empty."""
        db, _ = temp_db
        with db as conn:
            leads = conn.get_leads()
            assert leads == []

    def test_get_leads_with_filter(self, temp_db):
        """Test the status_filter functionality of get_leads."""
        db, _ = temp_db
        with db as conn:
            conn.insert_job_execution("job1", "step1", "input1", status="running")
            execution = conn.get_job_execution("job1", "step1")
            execution_id = execution['execution_id']

            # Insert leads first, then update status
            conn.insert_lead(execution_id, "place1", name="scraped", website="a.com")
            conn.update_lead("place1", execution_id=execution_id, status="scraped")
            
            conn.insert_lead(execution_id, "place2", name="not scraped", website="b.com")
            conn.update_lead("place2", execution_id=execution_id, status="pending")

            conn.insert_lead(execution_id, "place3", name="not scraped null", website="c.com")

            leads = conn.get_leads(status_filter="NOT scraped")
            assert len(leads) == 2
            assert "scraped" not in [lead['name'] for lead in leads]

    def test_update_lead(self, temp_db):
        """Test updating a lead's fields."""
        db, _ = temp_db
        with db as conn:
            conn.insert_job_execution("job1", "step1", "input1", status="running")
            execution = conn.get_job_execution("job1", "step1")
            execution_id = execution['execution_id']
            conn.insert_lead(execution_id, "place1", name="Original", website="a.com")
            conn.update_lead(place_id="place1", execution_id=execution_id, name="Updated", emails="test@example.com")
            
            # Retrieve the lead again to check if it was updated
            leads = conn.get_leads()
            updated_lead = next((l for l in leads if l['place_id'] == 'place1'), None)
            assert updated_lead is not None
            assert updated_lead['name'] == "Updated"
            assert updated_lead['emails'] == "test@example.com"

    def test_update_lead_stores_summary_fields(self, temp_db):
        """Test updating a lead with website summary fields."""
        db, _ = temp_db
        with db as conn:
            conn.insert_job_execution("job1", "step1", "input1", status="running")
            execution = conn.get_job_execution("job1", "step1")
            execution_id = execution['execution_id']
            conn.insert_lead(execution_id, "place1", name="Original", website="https://example.com")
            conn.update_lead(
                place_id="place1",
                execution_id=execution_id,
                website_summary="A useful public description of this business.",
                summary_source_url="https://example.com/about",
                summary_status="captured",
            )

            leads = conn.list_leads()
            updated_lead = next((lead for lead in leads if lead["place_id"] == "place1"), None)

            assert updated_lead is not None
            assert updated_lead["website_summary"] == "A useful public description of this business."
            assert updated_lead["summary_source_url"] == "https://example.com/about"
            assert updated_lead["summary_status"] == "captured"
            assert updated_lead["summary_updated_at"] is not None

    def test_insert_duplicate_lead_fails(self, temp_db):
        """Test that inserting a duplicate place_id fails globally."""
        db, db_path = temp_db
        with db as conn:
            conn.insert_job_execution("job1", "step1", "input1", status="running")
            conn.insert_job_execution("job2", "step1", "input2", status="running")
            execution = conn.get_job_execution("job1", "step1")
            second_execution = conn.get_job_execution("job2", "step1")
            execution_id = execution['execution_id']
            second_execution_id = second_execution['execution_id']
            conn.insert_lead(execution_id, "place1", name="Original", website="example.com")

        # Attempt to insert the same place from a different job.
        with pytest.raises(sqlite3.IntegrityError):
            with Database(db_path=db_path) as conn:
                conn.insert_lead(second_execution_id, "place1", name="Duplicate", website="example.com")

        # Verify that the second insert did not overwrite the original
        db_checker = Database(db_path=db_path)
        with db_checker as checker:
            leads = checker.get_leads()
            assert len(leads) == 1
            assert leads[0]['name'] == "Original"

    def test_migration_merges_duplicate_place_ids(self, tmp_path):
        """Test existing duplicate leads are merged into one canonical lead."""
        db_path = tmp_path / "duplicates.db"
        conn = sqlite3.connect(db_path)
        conn.executescript("""
            CREATE TABLE job_executions (
                execution_id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                step_id TEXT NOT NULL,
                input TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(job_id, step_id)
            );
            CREATE TABLE leads (
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
                lead_flag TEXT DEFAULT 'needs_review',
                lead_status TEXT DEFAULT 'new',
                notes TEXT,
                website_summary TEXT,
                summary_source_url TEXT,
                summary_status TEXT,
                summary_updated_at TIMESTAMP,
                UNIQUE(execution_id, place_id)
            );
            CREATE TABLE campaigns (
                campaign_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                business_type TEXT,
                search_location TEXT,
                filters_json TEXT,
                status TEXT DEFAULT 'draft',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE campaign_leads (
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
                UNIQUE(campaign_id, lead_id)
            );
            CREATE TABLE lead_emails (
                email_id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id INTEGER NOT NULL,
                email TEXT NOT NULL,
                category TEXT DEFAULT 'unknown',
                status TEXT DEFAULT 'new',
                is_primary BOOLEAN DEFAULT FALSE,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(lead_id, email)
            );
        """)
        conn.execute("INSERT INTO job_executions (job_id, step_id, input, status) VALUES ('job1', 'google_maps_scrape', 'dentist:London', 'completed')")
        conn.execute("INSERT INTO job_executions (job_id, step_id, input, status) VALUES ('job2', 'google_maps_scrape', 'dentist:London', 'completed')")
        conn.execute("""
            INSERT INTO leads (execution_id, place_id, location, name, website, emails, status, lead_status, notes)
            VALUES (1, 'same-place', 'dentist:London', 'Original', 'https://old.example', 'old@example.com', 'pending', 'new', NULL)
        """)
        conn.execute("""
            INSERT INTO leads (execution_id, place_id, location, name, phone, emails, status, lead_status, notes, website_summary)
            VALUES (2, 'same-place', 'dentist:London', 'Reviewed', '+123', 'new@example.com', 'scraped', 'ready', 'Keep this note', 'Useful context')
        """)
        conn.execute("INSERT INTO campaigns (name) VALUES ('Campaign')")
        conn.execute("INSERT INTO campaign_leads (campaign_id, lead_id, stage, final_email) VALUES (1, 2, 'approved', 'Approved copy')")
        conn.execute("INSERT INTO lead_emails (lead_id, email, category, status, is_primary) VALUES (1, 'old@example.com', 'info', 'valid', 1)")
        conn.execute("INSERT INTO lead_emails (lead_id, email, category, status, is_primary) VALUES (2, 'new@example.com', 'sales', 'valid', 1)")
        conn.commit()
        conn.close()

        Database(db_path=str(db_path)).initialize()

        with Database(db_path=str(db_path)) as migrated:
            leads = migrated.list_leads()
            assert len(leads) == 1
            lead = leads[0]
            assert lead["place_id"] == "same-place"
            assert lead["lead_status"] == "ready"
            assert lead["status"] == "scraped"
            assert lead["notes"] == "Keep this note"
            assert lead["website_summary"] == "Useful context"
            assert lead["campaign_count"] == 1
            assert lead["discovery_count"] == 2

            emails = migrated.list_lead_emails(lead["lead_id"])
            assert sorted(email["email"] for email in emails) == ["new@example.com", "old@example.com"]

            campaign_leads = migrated.list_campaign_leads(1)
            assert len(campaign_leads) == 1
            assert campaign_leads[0]["lead_id"] == lead["lead_id"]
            assert campaign_leads[0]["stage"] == "approved"
            assert campaign_leads[0]["final_email"] == "Approved copy"

            migrated.cursor.execute("SELECT COUNT(*) AS count FROM lead_discoveries WHERE lead_id = ?", (lead["lead_id"],))
            assert migrated.cursor.fetchone()["count"] == 2

            with pytest.raises(sqlite3.IntegrityError):
                migrated.insert_lead(lead["execution_id"], "same-place", name="Still duplicate")

    def test_initialize_twice_does_not_rerun_email_backfill(self, tmp_path):
        """Test versioned initialization avoids repeated legacy email backfills."""
        db_path = tmp_path / "versioned.db"
        conn = sqlite3.connect(db_path)
        conn.executescript("""
            CREATE TABLE job_executions (
                execution_id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                step_id TEXT NOT NULL,
                input TEXT NOT NULL,
                status TEXT NOT NULL,
                UNIQUE(job_id, step_id)
            );
            CREATE TABLE leads (
                lead_id INTEGER PRIMARY KEY AUTOINCREMENT,
                execution_id INTEGER NOT NULL,
                place_id TEXT NOT NULL,
                website TEXT,
                emails TEXT,
                status TEXT
            );
        """)
        conn.execute("INSERT INTO job_executions (job_id, step_id, input, status) VALUES ('job1', 'google_maps_scrape', 'input', 'completed')")
        conn.execute("INSERT INTO leads (execution_id, place_id, emails) VALUES (1, 'place1', 'info@example.com')")
        conn.commit()
        conn.close()

        Database(db_path=str(db_path)).initialize()
        with Database(db_path=str(db_path)) as db:
            db.cursor.execute("SELECT COUNT(*) AS count FROM lead_emails")
            assert db.cursor.fetchone()["count"] == 1
            db.cursor.execute("UPDATE lead_emails SET category = 'sales', notes = 'reviewed'")

        Database(db_path=str(db_path)).initialize()
        with Database(db_path=str(db_path)) as db:
            db.cursor.execute("PRAGMA user_version")
            assert db.cursor.fetchone()[0] == 1
            db.cursor.execute("SELECT COUNT(*) AS count FROM lead_emails")
            assert db.cursor.fetchone()["count"] == 1
            db.cursor.execute("SELECT category, notes FROM lead_emails WHERE email = 'info@example.com'")
            email = db.cursor.fetchone()
            assert email["category"] == "sales"
            assert email["notes"] == "reviewed"

    def test_google_places_upsert_updates_source_fields_and_preserves_manual_fields(self, temp_db):
        """Test rediscovery updates canonical source fields without overwriting manual data."""
        db, _ = temp_db
        with db as conn:
            conn.insert_job_execution("job1", "google_maps_scrape", "dentist:London", status="completed")
            conn.insert_job_execution("job2", "google_maps_scrape", "dentist:Paris", status="completed")
            first_execution = conn.get_job_execution("job1", "google_maps_scrape")
            second_execution = conn.get_job_execution("job2", "google_maps_scrape")

            created = conn.upsert_google_places_lead(
                first_execution["execution_id"],
                "place1",
                location="dentist:London",
                name="Original Name",
                address="Old Address",
                phone="+111",
                website="https://old.example",
            )
            conn.update_lead(
                "place1",
                execution_id=first_execution["execution_id"],
                emails="manual@example.com",
                status="scraped",
                website_summary="Manual context",
                summary_status="captured",
            )
            updated = conn.upsert_google_places_lead(
                second_execution["execution_id"],
                "place1",
                location="dentist:Paris",
                name="Fresh Name",
                address="Fresh Address",
                phone="+222",
                website="https://fresh.example",
            )

            assert created["storage_status"] == "created"
            assert updated["storage_status"] == "updated"
            leads = conn.list_leads()
            assert len(leads) == 1
            lead = leads[0]
            assert lead["name"] == "Fresh Name"
            assert lead["address"] == "Fresh Address"
            assert lead["phone"] == "+222"
            assert lead["website"] == "https://fresh.example"
            assert lead["emails"] == "manual@example.com"
            assert lead["status"] == "scraped"
            assert lead["website_summary"] == "Manual context"
            assert lead["discovery_count"] == 2

    def test_discovery_filters_include_rediscovered_canonical_leads(self, temp_db):
        """Test job and location filters use discovery history, not only lead.execution_id."""
        db, _ = temp_db
        with db as conn:
            conn.insert_job_execution("job1", "google_maps_scrape", "dentist:London", status="completed")
            conn.insert_job_execution("job2", "google_maps_scrape", "dentist:Paris", status="completed")
            first_execution = conn.get_job_execution("job1", "google_maps_scrape")
            second_execution = conn.get_job_execution("job2", "google_maps_scrape")
            conn.upsert_google_places_lead(
                first_execution["execution_id"],
                "place1",
                location="dentist:London",
                name="Clinic",
                website="https://clinic.example",
            )
            conn.upsert_google_places_lead(
                second_execution["execution_id"],
                "place1",
                location="dentist:Paris",
                name="Clinic Paris",
                website="https://clinic.example",
            )

            by_second_job = conn.list_leads(job_id="job2")
            assert len(by_second_job) == 1
            assert by_second_job[0]["place_id"] == "place1"
            assert by_second_job[0]["job_id"] == "job1"
            assert by_second_job[0]["last_discovery_job_id"] == "job2"

            by_location = conn.list_leads(business_type="dentist", search_location="Paris")
            assert len(by_location) == 1
            assert by_location[0]["place_id"] == "place1"

            options = conn.list_lead_filter_options()
            assert {"value": "dentist", "count": 2} in options["business_types"]
            assert {"value": "London", "count": 1} in options["search_locations"]
            assert {"value": "Paris", "count": 1} in options["search_locations"]

    def test_create_campaign_from_lead_filters(self, temp_db):
        """Test creating a campaign from existing lead filters."""
        db, _ = temp_db
        with db as conn:
            conn.insert_job_execution("job1", "google_maps_scrape", "dentist:London, UK", status="completed")
            execution = conn.get_job_execution("job1", "google_maps_scrape")
            execution_id = execution["execution_id"]
            conn.insert_lead(
                execution_id=execution_id,
                place_id="place1",
                location="dentist:London, UK",
                name="Good Dentist",
                website="https://example.com",
                emails="hello@example.com",
            )
            conn.update_lead("place1", execution_id=execution_id, status="scraped")

            result = conn.create_campaign(
                "Dentists London May 2026",
                filters={"status": "scraped", "has_email": True, "business_type": "dentist", "search_location": "London, UK"},
            )

            assert result["added_leads"] == 1
            assert result["campaign"]["business_type"] == "dentist"
            assert result["campaign"]["search_location"] == "London, UK"

            campaign_leads = conn.list_campaign_leads(result["campaign"]["campaign_id"])
            assert len(campaign_leads) == 1
            assert campaign_leads[0]["stage"] == "review"

            leads = conn.list_leads()
            assert leads[0]["campaign_count"] == 1
            assert leads[0]["campaign_names"] == ["Dentists London May 2026"]

    def test_email_settings_and_business_rules_persist(self, temp_db):
        """Test AI email settings and business-type rules."""
        db, _ = temp_db
        with db as conn:
            settings = conn.get_email_settings()
            assert settings["provider"] == "openai"
            assert settings["model"]
            assert "system_prompt" in settings

            updated = conn.update_email_settings(
                provider="anthropic",
                model="claude-3-5-sonnet-latest",
                system_prompt="System",
                user_prompt="User",
            )
            assert updated["provider"] == "anthropic"
            assert updated["model"] == "claude-3-5-sonnet-latest"

            rule = conn.upsert_business_type_email_rule(
                "dentist",
                business_description="a dental practice",
                pain_point="manual patient intake",
                offer_angle="automated qualification",
                extra_instructions="keep it direct",
            )
            assert rule["business_type"] == "dentist"
            assert rule["pain_point"] == "manual patient intake"
            assert conn.list_business_type_email_rules()[0]["business_type"] == "dentist"

    def test_store_generated_email_draft_does_not_overwrite_final_email(self, temp_db):
        """Test generated drafts update draft/stage while preserving final email."""
        db, _ = temp_db
        with db as conn:
            conn.insert_job_execution("job1", "google_maps_scrape", "dentist:London, UK", status="completed")
            execution = conn.get_job_execution("job1", "google_maps_scrape")
            conn.insert_lead(
                execution["execution_id"],
                "place1",
                location="dentist:London, UK",
                name="Good Dentist",
                website="https://example.com",
                emails="hello@example.com",
            )
            result = conn.create_campaign("Campaign", filters={"has_email": True})
            campaign_lead = conn.list_campaign_leads(result["campaign"]["campaign_id"])[0]
            conn.update_campaign_lead(
                campaign_lead["campaign_lead_id"],
                final_email="Approved final email",
            )

            updated = conn.store_generated_email_draft(
                campaign_lead["campaign_lead_id"],
                "Generated draft email",
            )

            assert updated["email_draft"] == "Generated draft email"
            assert updated["final_email"] == "Approved final email"
            assert updated["stage"] == "drafted"

    def test_store_generated_email_keeps_blocked_stage(self, temp_db):
        """Test generation storage does not move blocked stages."""
        db, _ = temp_db
        with db as conn:
            conn.insert_job_execution("job1", "google_maps_scrape", "dentist:London, UK", status="completed")
            execution = conn.get_job_execution("job1", "google_maps_scrape")
            conn.insert_lead(
                execution["execution_id"],
                "place1",
                location="dentist:London, UK",
                name="Good Dentist",
                emails="hello@example.com",
            )
            result = conn.create_campaign("Campaign", filters={"has_email": True})
            campaign_lead = conn.list_campaign_leads(result["campaign"]["campaign_id"])[0]
            conn.update_campaign_lead(campaign_lead["campaign_lead_id"], stage="approved")

            updated = conn.store_generated_email_draft(campaign_lead["campaign_lead_id"], "Generated draft")

            assert updated["email_draft"] == "Generated draft"
            assert updated["stage"] == "approved"

    def test_default_email_category_rules_classify_new_email_rows(self, temp_db):
        """Test default local-part rules classify inserted lead emails."""
        db, _ = temp_db
        with db as conn:
            conn.insert_job_execution("job1", "google_maps_scrape", "hotel:Tirana", status="completed")
            execution = conn.get_job_execution("job1", "google_maps_scrape")
            conn.insert_lead(execution["execution_id"], "place1", name="Hotel")
            lead = conn.list_leads()[0]

            conn.cursor.execute("""
                INSERT INTO lead_emails (lead_id, email, category, status)
                VALUES (?, 'finance@example.com', 'unknown', 'new')
            """, (lead["lead_id"],))
            conn.cursor.execute("SELECT category FROM lead_emails WHERE email = 'finance@example.com'")
            assert conn.cursor.fetchone()["category"] == "finance"

    def test_email_category_rules_can_be_added_and_applied_to_unknowns(self, temp_db):
        """Test adding a rule and applying it to existing unknown emails only."""
        db, _ = temp_db
        with db as conn:
            conn.insert_job_execution("job1", "google_maps_scrape", "hotel:Tirana", status="completed")
            execution = conn.get_job_execution("job1", "google_maps_scrape")
            conn.insert_lead(execution["execution_id"], "place1", name="Hotel")
            lead = conn.list_leads()[0]

            conn.cursor.execute("""
                INSERT INTO lead_emails (lead_id, email, category, status)
                VALUES (?, 'concierge@example.com', 'unknown', 'new')
            """, (lead["lead_id"],))
            assert conn.list_unknown_email_local_parts()[0]["local_part"] == "concierge"

            rule = conn.upsert_email_category_rule("concierge", "reception")
            assert rule["category"] == "reception"

            result = conn.apply_email_category_rules_to_unknowns()
            assert result["updated_count"] == 1
            conn.cursor.execute("SELECT category FROM lead_emails WHERE email = 'concierge@example.com'")
            assert conn.cursor.fetchone()["category"] == "reception"

    def test_context_manager_commit(self, temp_db):
        """Test that changes are committed when the with block exits without an exception."""
        db, db_path = temp_db
        with db as conn:
            conn.insert_job_execution("job1", "step1", "input1", status="committed")

        # Reconnect to the database to check if the data was persisted
        new_conn = sqlite3.connect(db_path)
        cursor = new_conn.cursor()
        cursor.execute("SELECT status FROM job_executions WHERE job_id = 'job1'")
        status = cursor.fetchone()[0]
        new_conn.close()
        
        assert status == "committed"

    def test_context_manager_rollback(self, temp_db):
        """Test that changes are rolled back when an exception is raised."""
        db, db_path = temp_db
        try:
            with db as conn:
                conn.insert_job_execution("job1", "step1", "input1", status="should_rollback")
                raise ValueError("Test exception")
        except ValueError:
            pass  # Expected exception

        # Reconnect to the database to check that the data was not persisted
        new_conn = sqlite3.connect(db_path)
        cursor = new_conn.cursor()
        cursor.execute("SELECT * FROM job_executions WHERE job_id = 'job1'")
        result = cursor.fetchone()
        new_conn.close()

        assert result is None

    def test_foreign_key_constraint(self, temp_db):
        """Test that inserting a lead with a non-existent execution_id fails."""
        db, _ = temp_db
        with pytest.raises(sqlite3.IntegrityError):
            with db as conn:
                # Attempt to insert a lead with an execution_id that does not exist
                conn.insert_lead(execution_id=999, place_id="place1", website="test.com")

    @patch('os.path.join', return_value=os.path.join(Config.TEMP_PATH, "scraping.db"))
    def test_init_db_defaults_to_config_path(self, mock_join):
        """Test that the database path defaults to Config.TEMP_PATH if not provided."""
        with patch('backend.database.os.makedirs'):
            with patch('backend.database.sqlite3.connect'):
                 db = Database()
                 assert db.db_path == mock_join.return_value
                 mock_join.assert_called_once_with(Config.TEMP_PATH, "scraping.db")

    @patch('os.access', return_value=False)
    @patch('logging.error')
    def test_init_db_permission_error(self, mock_logging_error, mock_os_access):
        """Test that a PermissionError is logged if the directory is not writable."""
        db_path = "/nonexistent/path/test.db"
        with patch('os.makedirs'):
            Database(db_path=db_path).initialize()
            mock_os_access.assert_called()
            assert mock_logging_error.call_count > 0
            assert "Failed to initialize database" in mock_logging_error.call_args[0][0]
