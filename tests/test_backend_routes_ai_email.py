import os
import sys
from unittest.mock import patch

from flask import Flask

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.database import Database
from backend.routes.api import api_bp


def create_test_client(db_path):
    app = Flask(__name__)
    app.register_blueprint(api_bp, url_prefix="/api")
    app.config["TESTING"] = True
    Database(db_path=db_path).initialize()
    return app.test_client(), lambda: Database(db_path=db_path)


def seed_campaign_lead(db_path, stage="review", emails="hello@example.com", lead_status="new", final_email=None):
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
        db.update_lead_by_id(1, lead_status=lead_status, status="scraped")
        result = db.create_campaign("Dentists", filters={"has_email": bool(emails)})
        campaign_lead = db.list_campaign_leads(result["campaign"]["campaign_id"])[0]
        db.update_campaign_lead(campaign_lead["campaign_lead_id"], stage=stage, final_email=final_email)
        return campaign_lead["campaign_id"], campaign_lead["campaign_lead_id"]


def test_email_settings_endpoints_validate_and_update(tmp_path):
    db_path = str(tmp_path / "test.db")
    client, db_factory = create_test_client(db_path)

    with patch("backend.routes.api.Database", side_effect=db_factory):
        response = client.patch("/api/email-settings", json={"provider": "bad"})
        assert response.status_code == 400

        response = client.patch("/api/email-settings", json={
            "provider": "anthropic",
            "model": "claude-test",
            "system_prompt": "System",
            "user_prompt": "User",
        })
        assert response.status_code == 200
        assert response.get_json()["settings"]["provider"] == "anthropic"

        response = client.get("/api/email-settings")
        assert response.status_code == 200
        assert response.get_json()["settings"]["model"] == "claude-test"


def test_business_type_rule_endpoint_upserts(tmp_path):
    db_path = str(tmp_path / "test.db")
    client, db_factory = create_test_client(db_path)

    with patch("backend.routes.api.Database", side_effect=db_factory):
        response = client.put("/api/email-settings/business-types/dentist", json={
            "business_description": "a dental practice",
            "pain_point": "manual intake",
            "offer_angle": "automation",
            "extra_instructions": "specific",
        })
        assert response.status_code == 200
        assert response.get_json()["rule"]["pain_point"] == "manual intake"

        response = client.get("/api/email-settings/business-types")
        assert response.status_code == 200
        assert response.get_json()["count"] == 1


def test_generate_email_saves_draft_without_overwriting_final(tmp_path):
    db_path = str(tmp_path / "test.db")
    _, campaign_lead_id = seed_campaign_lead(db_path, final_email="Final approved")
    client, db_factory = create_test_client(db_path)

    with patch("backend.routes.api.Database", side_effect=db_factory):
        with patch("backend.routes.api.generate_email_draft", return_value="Generated draft"):
            response = client.post(f"/api/campaign-leads/{campaign_lead_id}/generate-email")

    assert response.status_code == 200
    payload = response.get_json()["campaign_lead"]
    assert payload["email_draft"] == "Generated draft"
    assert payload["final_email"] == "Final approved"
    assert payload["stage"] == "drafted"


def test_generate_email_blocks_do_not_contact(tmp_path):
    db_path = str(tmp_path / "test.db")
    _, campaign_lead_id = seed_campaign_lead(db_path, stage="do_not_contact")
    client, db_factory = create_test_client(db_path)

    with patch("backend.routes.api.Database", side_effect=db_factory):
        response = client.post(f"/api/campaign-leads/{campaign_lead_id}/generate-email")

    assert response.status_code == 400
    assert "Cannot generate email" in response.get_json()["error"]


def test_generate_email_reports_missing_api_key(tmp_path):
    db_path = str(tmp_path / "test.db")
    _, campaign_lead_id = seed_campaign_lead(db_path)
    client, db_factory = create_test_client(db_path)

    with patch("backend.routes.api.Database", side_effect=db_factory):
        with patch("backend.ai_email_service.Config.OPENAI_API_KEY", None):
            response = client.post(f"/api/campaign-leads/{campaign_lead_id}/generate-email")

    assert response.status_code == 502
    assert "OPENAI_API_KEY" in response.get_json()["error"]


def test_email_category_rule_routes_apply_unknowns(tmp_path):
    db_path = str(tmp_path / "test.db")
    Database(db_path=db_path).initialize()
    with Database(db_path=db_path) as db:
        db.insert_job_execution("job1", "google_maps_scrape", "hotel:Tirana", status="completed")
        execution = db.get_job_execution("job1", "google_maps_scrape")
        db.insert_lead(execution["execution_id"], "place1", name="Hotel")
        lead = db.list_leads()[0]
        db.cursor.execute("""
            INSERT INTO lead_emails (lead_id, email, category, status)
            VALUES (?, 'concierge@example.com', 'unknown', 'new')
        """, (lead["lead_id"],))

    client, db_factory = create_test_client(db_path)
    with patch("backend.routes.api.Database", side_effect=db_factory):
        response = client.get("/api/lead-emails/unknown")
        assert response.status_code == 200
        assert response.get_json()["local_parts"][0]["local_part"] == "concierge"

        response = client.put("/api/email-category-rules/concierge", json={"category": "reception"})
        assert response.status_code == 200
        assert response.get_json()["rule"]["category"] == "reception"

        response = client.post("/api/email-category-rules/apply")
        assert response.status_code == 200
        assert response.get_json()["updated_count"] == 1


def test_email_category_rule_route_rejects_unknown_category(tmp_path):
    db_path = str(tmp_path / "test.db")
    client, db_factory = create_test_client(db_path)

    with patch("backend.routes.api.Database", side_effect=db_factory):
        response = client.put("/api/email-category-rules/info", json={"category": "unknown"})

    assert response.status_code == 400
    assert "non-unknown" in response.get_json()["error"]
