from unittest.mock import MagicMock, patch

from backend.scripts.scraping.scrape_for_email import EmailScraper, clean_summary_text
from backend.scripts.scraping.html_context_cleaner import html_to_context_text


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


def test_html_to_context_text_removes_noise_and_keeps_full_body_content():
    html = """
    <body>
      <header><nav>Home Rooms Contact Book Now</nav></header>
      <div id="cookie-banner">
        We collect cookies to improve your experience.
        <button>Accept all cookies</button>
        <button>Manage preferences</button>
      </div>
      <main>
        <h1>AMH Hotel</h1>
        <p>AMH Hotel is a family-run hotel near the old town.</p>
        <h2>Rooms & Services</h2>
        <ul>
          <li>Sea-view rooms with breakfast included</li>
          <li>Airport transfers available on request</li>
          <li>Event hosting for small business groups</li>
        </ul>
      </main>
      <section class="about">
        <h2>About Us</h2>
        <p>Our team helps guests plan tours, transport, and local experiences.</p>
      </section>
      <footer>Privacy Policy | Cookie Settings | Terms</footer>
    </body>
    """

    cleaned = html_to_context_text(html)

    assert "# AMH Hotel" in cleaned
    assert "## Rooms & Services" in cleaned
    assert "- Sea-view rooms with breakfast included" in cleaned
    assert "## About Us" in cleaned
    assert "Our team helps guests plan tours" in cleaned
    assert "Accept all cookies" not in cleaned
    assert "Privacy Policy" not in cleaned
    assert "Home Rooms Contact" not in cleaned
