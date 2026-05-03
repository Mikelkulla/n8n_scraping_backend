from unittest.mock import patch

from backend.routes.api import _scrape_and_store_lead_enrichment


class FakeDatabase:
    updates = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def update_lead(self, **kwargs):
        self.updates.append(kwargs)


def test_enrichment_stores_captured_summary():
    FakeDatabase.updates = []
    lead = {
        "lead_id": 1,
        "place_id": "place1",
        "execution_id": 10,
        "website": "https://example.com",
    }

    with patch("backend.routes.api.Database", return_value=FakeDatabase()):
        with patch("backend.routes.api.scrape_emails_with_summary") as scrape:
            scrape.return_value = {
                "emails": ["hello@realbusiness.co"],
                "website_summary": "A useful public description of this business.",
                "summary_source_url": "https://example.com/about",
                "summary_status": "captured",
            }

            _scrape_and_store_lead_enrichment(lead, max_pages=5, use_tor=False, headless=True)

    assert FakeDatabase.updates[-1]["emails"] == "hello@realbusiness.co"
    assert FakeDatabase.updates[-1]["status"] == "scraped"
    assert FakeDatabase.updates[-1]["website_summary"] == "A useful public description of this business."
    assert FakeDatabase.updates[-1]["summary_source_url"] == "https://example.com/about"
    assert FakeDatabase.updates[-1]["summary_status"] == "captured"


def test_enrichment_stores_empty_summary_status():
    FakeDatabase.updates = []
    lead = {
        "lead_id": 1,
        "place_id": "place1",
        "execution_id": 10,
        "website": "https://example.com",
    }

    with patch("backend.routes.api.Database", return_value=FakeDatabase()):
        with patch("backend.routes.api.scrape_emails_with_summary") as scrape:
            scrape.return_value = {
                "emails": [],
                "website_summary": None,
                "summary_source_url": None,
                "summary_status": "empty",
            }

            _scrape_and_store_lead_enrichment(lead, max_pages=5, use_tor=False, headless=True)

    assert FakeDatabase.updates[-1]["emails"] is None
    assert FakeDatabase.updates[-1]["status"] == "scraped"
    assert FakeDatabase.updates[-1]["website_summary"] == ""
    assert FakeDatabase.updates[-1]["summary_source_url"] == ""
    assert FakeDatabase.updates[-1]["summary_status"] == "empty"


def test_enrichment_passes_parent_stop_signal_to_inner_scraper():
    FakeDatabase.updates = []
    lead = {
        "lead_id": 1,
        "place_id": "place1",
        "execution_id": 10,
        "website": "https://example.com",
    }

    with patch("backend.routes.api.check_stop_signal", return_value=False):
        with patch("backend.routes.api.Database", return_value=FakeDatabase()):
            with patch("backend.routes.api.scrape_emails_with_summary") as scrape:
                scrape.return_value = {
                    "emails": [],
                    "website_summary": None,
                    "summary_source_url": None,
                    "summary_status": "empty",
                }

                stopped = _scrape_and_store_lead_enrichment(
                    lead,
                    max_pages=5,
                    use_tor=False,
                    headless=True,
                    stop_job_id="parent-job",
                    stop_step_id="leads_email_scrape",
                )

    assert stopped is False
    assert scrape.call_args.kwargs["stop_job_id"] == "parent-job"
    assert scrape.call_args.kwargs["stop_step_id"] == "leads_email_scrape"


def test_enrichment_skips_lead_update_when_stop_arrives_after_inner_scrape():
    FakeDatabase.updates = []
    lead = {
        "lead_id": 1,
        "place_id": "place1",
        "execution_id": 10,
        "website": "https://example.com",
    }

    with patch("backend.routes.api.check_stop_signal", side_effect=[False, True]):
        with patch("backend.routes.api.Database", return_value=FakeDatabase()):
            with patch("backend.routes.api.scrape_emails_with_summary") as scrape:
                scrape.return_value = {
                    "emails": ["hello@realbusiness.co"],
                    "website_summary": "A useful public description of this business.",
                    "summary_source_url": "https://example.com/about",
                    "summary_status": "captured",
                }

                stopped = _scrape_and_store_lead_enrichment(
                    lead,
                    max_pages=5,
                    use_tor=False,
                    headless=True,
                    stop_job_id="parent-job",
                    stop_step_id="leads_email_scrape",
                )

    assert stopped is True
    assert FakeDatabase.updates == []
