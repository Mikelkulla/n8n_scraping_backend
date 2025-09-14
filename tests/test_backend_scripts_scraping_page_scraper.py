import unittest
from unittest.mock import patch, MagicMock
import logging
from backend.scripts.scraping.page_scraper import scrape_page

class TestPageScraper(unittest.TestCase):

    @patch('backend.scripts.scraping.page_scraper.extract_emails_from_page')
    def test_scrape_page_success(self, mock_extract_emails):
        """Test that scrape_page successfully returns emails."""
        # Arrange
        mock_driver = MagicMock()
        test_url = "http://example.com"
        expected_emails = {"test@example.com", "another@example.com"}
        mock_extract_emails.return_value = expected_emails

        # Act
        result = scrape_page(mock_driver, test_url)

        # Assert
        self.assertEqual(result, expected_emails)
        mock_extract_emails.assert_called_once_with(mock_driver, test_url)

    @patch('backend.scripts.scraping.page_scraper.extract_emails_from_page')
    def test_scrape_page_exception(self, mock_extract_emails):
        """Test that scrape_page returns an empty set when an exception occurs."""
        # Arrange
        mock_driver = MagicMock()
        test_url = "http://example.com"
        mock_extract_emails.side_effect = Exception("Test exception")

        # Act
        with self.assertLogs('backend.scripts.scraping.page_scraper', level='ERROR') as cm:
            result = scrape_page(mock_driver, test_url)
            # Assert
            self.assertEqual(len(cm.output), 1)
            self.assertIn("Error scraping http://example.com: Test exception", cm.output[0])

        # Assert
        self.assertEqual(result, set())
        mock_extract_emails.assert_called_once_with(mock_driver, test_url)

    @patch('backend.scripts.scraping.page_scraper.extract_emails_from_page')
    @patch('backend.scripts.scraping.page_scraper.logger.info')
    def test_scrape_page_logging(self, mock_logger_info, mock_extract_emails):
        """Test that scrape_page logs the URL it is visiting."""
        # Arrange
        mock_driver = MagicMock()
        test_url = "http://example.com"
        mock_extract_emails.return_value = set()

        # Act
        scrape_page(mock_driver, test_url)

        # Assert
        mock_logger_info.assert_called_with(f"Visiting URL: {test_url}")
