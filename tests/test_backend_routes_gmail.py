import os
import sys
from unittest.mock import patch

from flask import Flask

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.database import Database
from backend.gmail_service import GmailIntegrationError
from backend.routes.api import api_bp


def create_test_client(db_path):
    app = Flask(__name__)
    app.register_blueprint(api_bp, url_prefix="/api")
    app.config["TESTING"] = True
    Database(db_path=db_path).initialize()
    return app.test_client(), lambda: Database(db_path=db_path)


def seed_campaign_lead(db_path, stage="approved", emails="hello@gooddentist.co", final_email="Reviewed copy"):
    Database(db_path=db_path).initialize()
    with Database(db_path=db_path) as db:
        db.insert_job_execution("job1", "google_maps_scrape", "dentist:London, UK", status="completed")
        execution = db.get_job_execution("job1", "google_maps_scrape")
        db.insert_lead(
            execution["execution_id"],
            "place1",
            location="dentist:London, UK",
            name="Good Dentist",
            website="https://example.com",
            emails=emails,
        )
        db.update_lead_by_id(1, lead_status="ready", status="scraped")
        result = db.create_campaign("Dentists", filters={"has_email": bool(emails)})
        campaign_lead = db.list_campaign_leads(result["campaign"]["campaign_id"])[0]
        updated = db.update_campaign_lead(
            campaign_lead["campaign_lead_id"],
            stage=stage,
            final_email=final_email,
        )
        return updated["campaign_id"], updated["campaign_lead_id"]


def test_gmail_status_hides_tokens(tmp_path):
    db_path = str(tmp_path / "test.db")
    client, _ = create_test_client(db_path)

    with patch("backend.routes.api.get_gmail_status", return_value={
        "configured": True,
        "authenticated": False,
        "account_email": None,
        "scopes": ["https://www.googleapis.com/auth/gmail.compose"],
        "client_secret_path": "config/gmail_client_secret.json",
        "token_path": "backend/temp/gmail_token.json",
    }):
        response = client.get("/api/gmail/status")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["gmail"]["configured"] is True
    assert "refresh_token" not in str(payload)
    assert "access_token" not in str(payload)


def test_gmail_auth_start_reports_missing_config(tmp_path):
    db_path = str(tmp_path / "test.db")
    client, _ = create_test_client(db_path)

    with patch("backend.routes.api.start_gmail_auth", side_effect=GmailIntegrationError("missing client secret")):
        response = client.post("/api/gmail/auth/start", json={})

    assert response.status_code == 400
    assert "missing client secret" in response.get_json()["error"]


def test_create_gmail_draft_requires_final_email(tmp_path):
    db_path = str(tmp_path / "test.db")
    _, campaign_lead_id = seed_campaign_lead(db_path, final_email="")
    client, db_factory = create_test_client(db_path)

    with patch("backend.routes.api.Database", side_effect=db_factory):
        response = client.post(f"/api/campaign-leads/{campaign_lead_id}/gmail-draft")

    assert response.status_code == 400
    assert "final_email" in response.get_json()["error"]


def test_create_gmail_draft_blocks_contacted_stage(tmp_path):
    db_path = str(tmp_path / "test.db")
    _, campaign_lead_id = seed_campaign_lead(db_path, stage="contacted")
    client, db_factory = create_test_client(db_path)

    with patch("backend.routes.api.Database", side_effect=db_factory):
        response = client.post(f"/api/campaign-leads/{campaign_lead_id}/gmail-draft")

    assert response.status_code == 400
    assert "contacted" in response.get_json()["error"]


def test_create_gmail_draft_stores_metadata_without_overwriting_copy(tmp_path):
    db_path = str(tmp_path / "test.db")
    _, campaign_lead_id = seed_campaign_lead(db_path, stage="drafted", final_email="Reviewed final")
    client, db_factory = create_test_client(db_path)

    with patch("backend.routes.api.Database", side_effect=db_factory):
        with patch("backend.routes.api.create_gmail_draft", return_value={"draft_id": "draft-1", "message_id": "msg-1"}) as create:
            response = client.post(f"/api/campaign-leads/{campaign_lead_id}/gmail-draft")

    assert response.status_code == 200
    create.assert_called_once()
    payload = response.get_json()["campaign_lead"]
    assert payload["gmail_draft_id"] == "draft-1"
    assert payload["gmail_message_id"] == "msg-1"
    assert payload["gmail_draft_status"] == "created"
    assert payload["final_email"] == "Reviewed final"
    assert payload["stage"] == "approved"


def test_create_gmail_draft_persists_safe_error(tmp_path):
    db_path = str(tmp_path / "test.db")
    _, campaign_lead_id = seed_campaign_lead(db_path)
    client, db_factory = create_test_client(db_path)

    with patch("backend.routes.api.Database", side_effect=db_factory):
        with patch("backend.routes.api.create_gmail_draft", side_effect=GmailIntegrationError("Gmail is not authenticated")):
            response = client.post(f"/api/campaign-leads/{campaign_lead_id}/gmail-draft")

    assert response.status_code == 400
    with Database(db_path=db_path) as db:
        lead = db.get_campaign_lead(campaign_lead_id)
    assert lead["gmail_draft_status"] == "failed"
    assert lead["gmail_error"] == "Gmail is not authenticated"
