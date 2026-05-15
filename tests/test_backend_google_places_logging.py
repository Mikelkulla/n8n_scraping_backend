import logging

from backend.scripts.google_api.google_places import _log_places_request


def test_places_debug_logging_redacts_api_key(caplog):
    caplog.set_level(logging.DEBUG)

    _log_places_request(
        "POST",
        "https://places.googleapis.com/v1/places:searchText",
        headers={"X-Goog-Api-Key": "secret-google-key"},
        json={"textQuery": "dentist in London"},
    )

    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert "POST https://places.googleapis.com/v1/places:searchText" in log_text
    assert "dentist in London" in log_text
    assert "secret-google-key" not in log_text
    assert "<redacted>" in log_text
