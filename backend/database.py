import sqlite3
import os
from backend.config import Config
# from config import Config
import logging

def init_db():
    """
    Initialize the SQLite database and create the job_executions and leads tables if they don't exist.
    """
    db_path = os.path.join(Config.TEMP_PATH, "scraping.db")
    try:
        os.makedirs(Config.TEMP_PATH, exist_ok=True)
        if not os.access(Config.TEMP_PATH, os.W_OK):
            raise PermissionError(f"No write permission for {Config.TEMP_PATH}")
        conn = sqlite3.connect(db_path)
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
        logging.info(f"Database initialized at {db_path}")
    except (sqlite3.Error, PermissionError, OSError) as e:
        logging.error(f"Failed to initialize database: {e}")
    finally:
        if conn:
            conn.close()

def insert_job_execution(job_id, step_id, input, max_pages=None, use_tor=None, headless=None, status=None, stop_call=False, error_message=None, current_row=None, total_rows=None):
    """
    Insert or replace a job execution record in the job_executions table.
    """
    conn = sqlite3.connect(os.path.join(Config.TEMP_PATH, "scraping.db"))
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO job_executions (
                job_id, step_id, input, max_pages, use_tor, headless, status, stop_call,
                error_message, current_row, total_rows, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (job_id, step_id, input, max_pages, use_tor, headless, status, stop_call, error_message, current_row, total_rows))
        conn.commit()
        logging.info(f"Inserted/Updated execution for job {job_id}, step {step_id}")
    except sqlite3.Error as e:
        logging.error(f"Failed to insert/update execution for job {job_id}: {e}")
    finally:
        conn.close()

def update_job_execution(job_id, step_id, current_row=None, total_rows=None, status=None, error_message=None, stop_call=None):
    """
    Update specific fields in a job execution record identified by job_id and step_id.
    """
    conn = sqlite3.connect(os.path.join(Config.TEMP_PATH, "scraping.db"))
    try:
        cursor = conn.cursor()
        # Build the SET clause dynamically based on provided parameters
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
        # Always update the updated_at timestamp
        set_clauses.append("updated_at = CURRENT_TIMESTAMP")

        if not set_clauses:
            logging.warning(f"No fields to update for job {job_id}, step {step_id}")
            return

        query = f"UPDATE job_executions SET {', '.join(set_clauses)} WHERE job_id = ? AND step_id = ?"
        params.extend([job_id, step_id])

        cursor.execute(query, params)
        if cursor.rowcount == 0:
            logging.warning(f"No record found to update for job {job_id}, step {step_id}")
        else:
            conn.commit()
            logging.info(f"Updated execution for job {job_id}, step {step_id}")
    except sqlite3.Error as e:
        logging.error(f"Failed to update execution for job {job_id}: {e}")
    finally:
        conn.close()

def get_job_execution(job_id, step_id):
    """
    Retrieve a job execution record for the given job_id and step_id.
    """
    conn = sqlite3.connect(os.path.join(Config.TEMP_PATH, "scraping.db"))
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM job_executions WHERE job_id = ? AND step_id = ?
        """, (job_id, step_id))
        row = cursor.fetchone()
        return dict(row) if row else None
    except sqlite3.Error as e:
        logging.error(f"Failed to fetch execution for job {job_id}: {e}")
        return None
    finally:
        conn.close()

def get_leads():
    """
    Retrieve all leads from the leads table. (Where website is not null)
    Returns:
        List of dictionaries containing lead records, or empty list if none found or on error.
    """
    conn = sqlite3.connect(os.path.join(Config.TEMP_PATH, "scraping.db"))
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM leads WHERE website IS NOT NULL")
        rows = cursor.fetchall()
        return [dict(row) for row in rows] if rows else []
    except sqlite3.Error as e:
        logging.error(f"Failed to fetch leads: {e}")
        return []
    finally:
        conn.close()

def insert_lead(conn, job_id, place_id, location=None, name=None, address=None, phone=None, website=None, emails=None):
    """
    Insert or replace a lead record in the leads table.

    Args:
        conn (sqlite3.Connection): SQLite database connection.
        job_id (str): Job ID linking to job_executions.
        place_id (str): Google Place ID.
        location (str, optional): Location name (e.g., "Sarande, Albania").
        name (str, optional): Place name.
        address (str, optional): Formatted address.
        phone (str, optional): International phone number.
        website (str, optional): Website URL.
        emails (str, optional): Comma-separated emails (nullable for now).
    """
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO leads (
                job_id, place_id, location, name, address, phone, website, emails, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (job_id, place_id, location, name, address, phone, website, emails))
        conn.commit()
        logging.info(f"Inserted/Updated lead for job {job_id}, place {place_id}")
    except sqlite3.Error as e:
        logging.error(f"Failed to insert/update lead for job {job_id}, place {place_id}: {e}")

def update_lead(conn, job_id, place_id, location=None, name=None, address=None, phone=None, website=None, emails=None, status=None):
    """
    Update specific fields in a lead record identified by job_id and place_id.

    Args:
        conn (sqlite3.Connection): SQLite database connection.
        job_id (str): Job ID linking to job_executions.
        place_id (str): Google Place ID.
        location (str, optional): Location name (e.g., "Sarande, Albania").
        name (str, optional): Place name.
        address (str, optional): Formatted address.
        phone (str, optional): International phone number.
        website (str, optional): Website URL.
        emails (str, optional): Comma-separated emails.
    """
    try:
        cursor = conn.cursor()
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

        # query = f"UPDATE leads SET {', '.join(set_clauses)} WHERE job_id = ? AND place_id = ?"
        # params.extend([job_id, place_id])
        query = f"UPDATE leads SET {', '.join(set_clauses)} WHERE place_id = ?"
        params.extend([place_id])
        cursor.execute(query, params)
        if cursor.rowcount == 0:
            logging.warning(f"No record found to update for lead with job {job_id}, place {place_id}")
        else:
            conn.commit()
            logging.info(f"Updated lead for job {job_id}, place {place_id}")
    except sqlite3.Error as e:
        logging.error(f"Failed to update lead for job {job_id}, place {place_id}: {e}")

if __name__ == "__main__":
    # init_db()
    print(get_leads()[300])