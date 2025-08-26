import sqlite3
import os
import logging
import threading
from backend.config import Config

class Database:
    _lock = threading.RLock()

    def __init__(self, db_path=None):
        if db_path is None:
            self.db_path = os.path.join(Config.TEMP_PATH, "scraping.db")
        else:
            self.db_path = db_path
        self.conn = None
        self.cursor = None
        self._init_db()

    def _init_db(self):
        """
        Initialize the SQLite database and create the tables if they don't exist.
        """
        try:
            # Ensure the directory exists and is writable
            db_dir = os.path.dirname(self.db_path)
            os.makedirs(db_dir, exist_ok=True)
            if not os.access(db_dir, os.W_OK):
                raise PermissionError(f"No write permission for {db_dir}")

            # Connect to the database to create tables
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Enable foreign key support
            cursor.execute("PRAGMA foreign_keys = ON")

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

            # Create leads table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS leads (
                    lead_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    place_id TEXT NOT NULL,
                    location TEXT,
                    name TEXT,
                    address TEXT,
                    phone TEXT,
                    website TEXT,
                    emails TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(job_id, place_id),
                    FOREIGN KEY (job_id) REFERENCES job_executions(job_id)
                )
            """)
            conn.commit()
            logging.info(f"Database initialized at {self.db_path}")
        except (sqlite3.Error, PermissionError, OSError) as e:
            logging.error(f"Failed to initialize database: {e}")
        finally:
            if conn:
                conn.close()

    def __enter__(self):
        Database._lock.acquire()
        self.conn = sqlite3.connect(self.db_path, timeout=10.0)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            if exc_type is None:
                self.conn.commit()
            else:
                self.conn.rollback()
            self.conn.close()
            self.conn = None
        Database._lock.release()

    def insert_job_execution(self, job_id, step_id, input, max_pages=None, use_tor=None, headless=None, status=None, stop_call=False, error_message=None, current_row=None, total_rows=None):
        try:
            self.cursor.execute("""
                INSERT OR REPLACE INTO job_executions (
                    job_id, step_id, input, max_pages, use_tor, headless, status, stop_call,
                    error_message, current_row, total_rows, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (job_id, step_id, input, max_pages, use_tor, headless, status, stop_call, error_message, current_row, total_rows))
            logging.info(f"Inserted/Updated execution for job {job_id}, step {step_id}")
        except sqlite3.Error as e:
            logging.error(f"Failed to insert/update execution for job {job_id}: {e}")

    def update_job_execution(self, job_id, step_id, current_row=None, total_rows=None, status=None, error_message=None, stop_call=None):
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

    def get_job_execution(self, job_id, step_id):
        try:
            self.cursor.execute("""
                SELECT * FROM job_executions WHERE job_id = ? AND step_id = ?
            """, (job_id, step_id))
            row = self.cursor.fetchone()
            return dict(row) if row else None
        except sqlite3.Error as e:
            logging.error(f"Failed to fetch execution for job {job_id}: {e}")
            return None

    def get_leads(self, status_filter=None):
        try:
            query = "SELECT * FROM leads WHERE website IS NOT NULL"
            if status_filter == "NOT scraped":
                query += " AND (status IS NULL OR status != 'scraped')"
            self.cursor.execute(query)
            rows = self.cursor.fetchall()
            return [dict(row) for row in rows] if rows else []
        except sqlite3.Error as e:
            logging.error(f"Failed to fetch leads: {e}")
            return []

    def insert_lead(self, job_id, place_id, location=None, name=None, address=None, phone=None, website=None, emails=None):
        try:
            self.cursor.execute("""
                INSERT OR REPLACE INTO leads (
                    job_id, place_id, location, name, address, phone, website, emails, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (job_id, place_id, location, name, address, phone, website, emails))
            logging.info(f"Inserted/Updated lead for job {job_id}, place {place_id}")
        except sqlite3.Error as e:
            logging.error(f"Failed to insert/update lead for job {job_id}, place {place_id}: {e}")

    def update_lead(self, job_id, place_id, location=None, name=None, address=None, phone=None, website=None, emails=None, status=None):
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
            set_clauses.append("updated_at = CURRENT_TIMESTAMP")

            if not set_clauses:
                logging.warning(f"No fields to update for lead with job {job_id}, place {place_id}")
                return

            query = f"UPDATE leads SET {', '.join(set_clauses)} WHERE place_id = ?"
            params.extend([place_id])
            self.cursor.execute(query, params)
            if self.cursor.rowcount == 0:
                logging.warning(f"No record found to update for lead with job {job_id}, place {place_id}")
            else:
                logging.info(f"Updated lead for job {job_id}, place {place_id}")
        except sqlite3.Error as e:
            logging.error(f"Failed to update lead for job {job_id}, place {place_id}: {e}")

if __name__ == "__main__":
    with Database() as db:
        leads = db.get_leads()
        if leads and len(leads) > 300:
            print(leads[300])