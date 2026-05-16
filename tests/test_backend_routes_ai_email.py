import os
import sys
import logging
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


def test_app_settings_endpoint_updates_and_hides_secrets(tmp_path):
    db_path = str(tmp_path / "test.db")
    client, db_factory = create_test_client(db_path)

    with patch("backend.routes.api.Database", side_effect=db_factory):
        response = client.get("/api/app-settings")
        assert response.status_code == 200
        payload = response.get_json()
        assert payload["settings"]["log_level"]
        assert "OPENAI_API_KEY" not in str(payload)
        assert "ANTHROPIC_API_KEY" not in str(payload)
        assert "GOOGLE_API_KEY" not in str(payload)

        response = client.patch("/api/app-settings", json={
            "log_level": "debug",
            "scraper_max_pages": 12,
            "scraper_sitemap_limit": 7,
            "scraper_headless": False,
            "scraper_use_tor": True,
            "scraper_max_threads": 3,
            "places_place_type": "dentist",
            "places_max_places": 15,
            "places_radius": 500,
        })
        assert response.status_code == 200
        settings = response.get_json()["settings"]
        assert settings["log_level"] == "DEBUG"
        assert settings["scraper_max_pages"] == 12
        assert settings["scraper_headless"] is False
        assert settings["scraper_use_tor"] is True
        assert settings["places_place_type"] == "dentist"

        response = client.patch("/api/app-settings", json={"scraper_max_pages": 0})
        assert response.status_code == 400


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


def test_api_info_logs_method_and_path_only(tmp_path, caplog):
    db_path = str(tmp_path / "test.db")
    _, campaign_lead_id = seed_campaign_lead(db_path, final_email="Final approved")
    client, db_factory = create_test_client(db_path)

    caplog.set_level(logging.INFO)
    caplog.clear()
    with patch("backend.routes.api.Database", side_effect=db_factory):
        with patch("backend.routes.api.generate_email_draft", return_value="Generated draft"):
            response = client.post(f"/api/campaign-leads/{campaign_lead_id}/generate-email")

    assert response.status_code == 200
    api_records = [
        record for record in caplog.records
        if getattr(record, "log_tag", None) == "api"
        and record.getMessage() == f"POST /api/campaign-leads/{campaign_lead_id}/generate-email"
    ]
    assert api_records
    assert "Generated draft" not in "\n".join(record.getMessage() for record in caplog.records if record.levelno == logging.INFO)


def test_generate_email_allows_approved_lead_manual_regeneration(tmp_path):
    db_path = str(tmp_path / "test.db")
    _, campaign_lead_id = seed_campaign_lead(db_path, stage="approved", final_email="Final approved")
    client, db_factory = create_test_client(db_path)

    with patch("backend.routes.api.Database", side_effect=db_factory):
        with patch("backend.routes.api.generate_email_draft", return_value="Generated draft"):
            response = client.post(f"/api/campaign-leads/{campaign_lead_id}/generate-email")

    assert response.status_code == 200
    payload = response.get_json()["campaign_lead"]
    assert payload["email_draft"] == "Generated draft"
    assert payload["final_email"] == "Final approved"
    assert payload["stage"] == "approved"


def test_bulk_generate_emails_skips_approved_leads(tmp_path):
    db_path = str(tmp_path / "test.db")
    campaign_id, _ = seed_campaign_lead(db_path, stage="approved", final_email="Final approved")
    client, db_factory = create_test_client(db_path)

    with patch("backend.routes.api.Database", side_effect=db_factory):
        with patch("backend.routes.api.generate_email_draft", return_value="Generated draft") as generate:
            response = client.post(f"/api/campaigns/{campaign_id}/generate-emails", json={"limit": 25})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["generated_count"] == 0
    assert payload["skipped_count"] == 1
    assert "approved" in payload["skipped"][0]["reason"]
    generate.assert_not_called()


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


def test_openai_gpt5_payload_omits_temperature():
    from backend.ai_email_service import _generate_openai

    class FakeResponse:
        status_code = 200
        text = ""

        def json(self):
            return {"choices": [{"message": {"content": "Draft"}}]}

    with patch("backend.ai_email_service.Config.OPENAI_API_KEY", "key"):
        with patch("backend.ai_email_service.requests.post", return_value=FakeResponse()) as post:
            assert _generate_openai("gpt-5.1", "System", "User") == "Draft"
            assert "temperature" not in post.call_args.kwargs["json"]

        with patch("backend.ai_email_service.requests.post", return_value=FakeResponse()) as post:
            assert _generate_openai("gpt-4.1-mini", "System", "User") == "Draft"
            assert post.call_args.kwargs["json"]["temperature"] == 0.5


def test_generate_email_subject_uses_provider_and_cleans_subject():
    from backend.ai_email_service import generate_email_subject

    lead = {
        "name": "Good Dentist",
        "business_type": "dentist",
        "final_email": "Reviewed final email body",
    }
    settings = {
        "provider": "openai",
        "model": "gpt-4.1-mini",
    }

    with patch("backend.ai_email_service._generate_openai", return_value='Subject: "Less admin for Good Dentist"') as generate:
        subject = generate_email_subject(lead, settings)

    assert subject == "Less admin for Good Dentist"
    generate.assert_called_once()


def test_openai_logging_redacts_secret_request_and_response_content(caplog):
    from backend.ai_email_service import _generate_openai

    class FakeResponse:
        status_code = 200
        text = "provider text with generated body"

        def json(self):
            return {"choices": [{"message": {"content": "Generated secret draft"}}]}

    caplog.set_level(logging.DEBUG)
    with patch("backend.ai_email_service.Config.OPENAI_API_KEY", "secret-api-key"):
        with patch("backend.ai_email_service.requests.post", return_value=FakeResponse()):
            assert _generate_openai("gpt-4.1-mini", "System secret", "User secret prompt") == "Generated secret draft"

    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert "https://api.openai.com/v1/chat/completions" in log_text
    assert "secret-api-key" not in log_text
    assert "System secret" not in log_text
    assert "User secret prompt" not in log_text
    assert "Generated secret draft" not in log_text


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
