from unittest.mock import MagicMock, patch

from backend.scripts.scraping.scrape_for_email import EmailScraper, clean_summary_text


def test_summary_capture_uses_homepage_only():
    scraper = EmailScraper("job1", "email_scrape", "https://example.com")
    scraper.driver = MagicMock()
    scraper.urls_to_visit = [
        "https://example.com/about-us",
        "https://example.com/contact",
    ]

    with patch("backend.scripts.scraping.scrape_for_email.check_stop_signal", return_value=False):
        with patch("backend.scripts.scraping.scrape_for_email.scrape_page_content") as scrape_page_content:
            scrape_page_content.return_value = {
                "emails": set(),
                "body_text": "Example Inn is a family-run hotel with sea-view rooms, local dining, and guided tours for guests visiting the coast.",
            }

            scraper._capture_summary()

    scrape_page_content.assert_called_once_with(scraper.driver, "https://example.com")
    assert scraper.summary_source_url == "https://example.com"
    assert scraper.summary_status == "captured"


def test_clean_summary_text_drops_navigation_footer_and_caps_text():
    raw_text = """
    Home
    Menu
    Welcome to Example Inn, a family-run hotel with sea-view rooms, local dining, and guided tours for guests visiting the coast.
    Privacy Policy
    Copyright 2026 Example Inn. All rights reserved.
    Our restaurant serves regional food from nearby farms and hosts private dinners for small groups throughout the year.
    """

    cleaned = clean_summary_text(raw_text, max_chars=120)

    assert "Welcome to Example Inn" in cleaned
    assert "Privacy Policy" not in cleaned
    assert "Copyright" not in cleaned
    assert len(cleaned) <= 120
