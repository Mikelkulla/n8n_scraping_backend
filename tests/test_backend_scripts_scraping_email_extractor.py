import unittest
from unittest.mock import Mock, patch
from backend.scripts.scraping.email_extractor import extract_emails_from_text, extract_emails_from_page

class TestEmailExtractor(unittest.TestCase):

    def test_extract_emails_from_text_single(self):
        text = "Contact us at contact@mydomain.com."
        self.assertEqual(extract_emails_from_text(text), {"contact@mydomain.com"})

    def test_extract_emails_from_text_multiple(self):
        text = "Emails: one@mydomain.com, two@mydomain.com."
        self.assertEqual(extract_emails_from_text(text), {"one@mydomain.com", "two@mydomain.com"})

    def test_extract_emails_from_text_duplicates(self):
        text = "Email us at support@mydomain.com or support@mydomain.com."
        self.assertEqual(extract_emails_from_text(text), {"support@mydomain.com"})

    def test_extract_emails_from_text_no_emails(self):
        text = "There are no emails here."
        self.assertEqual(extract_emails_from_text(text), set())

    def test_extract_emails_from_text_example_domains(self):
        text = "My email is user@test.com and another is user@example.org"
        self.assertEqual(extract_emails_from_text(text), set())

    def test_extract_emails_from_text_mixed_case(self):
        text = "Contact us at Support@Mydomain.com."
        self.assertEqual(extract_emails_from_text(text), {"Support@Mydomain.com"})

    def test_extract_emails_from_text_with_special_chars(self):
        text = "Emails: first.last@mydomain.com, first_last@mydomain.com, first+last@mydomain.com."
        self.assertEqual(extract_emails_from_text(text), {"first.last@mydomain.com", "first_last@mydomain.com", "first+last@mydomain.com"})

    @patch('backend.scripts.scraping.email_extractor.extract_emails_from_text')
    @patch('selenium.webdriver.remote.webdriver.WebDriver')
    def test_extract_emails_from_page_body_and_mailto(self, mock_driver, mock_extract_emails_from_text):
        # Configure the mock for body text extraction
        mock_driver.add_human_behavior = Mock()
        mock_body = Mock()
        mock_body.text = "Contact us at body.email@mydomain.com"
        mock_driver.find_element.return_value = mock_body
        mock_extract_emails_from_text.return_value = {"body.email@mydomain.com"}

        # Configure the mock for mailto links
        mock_link = Mock()
        mock_link.get_attribute.return_value = "mailto:mailto.email@mydomain.com"
        mock_driver.find_elements.return_value = [mock_link]

        # Execute the function
        emails = extract_emails_from_page(mock_driver, "http://anyurl.com")

        # Assert the results
        self.assertEqual(emails, {"body.email@mydomain.com", "mailto.email@mydomain.com"})
        mock_driver.get.assert_called_with("http://anyurl.com")
        mock_extract_emails_from_text.assert_called_with("Contact us at body.email@mydomain.com")

    @patch('selenium.webdriver.remote.webdriver.WebDriver')
    def test_extract_emails_from_page_no_emails(self, mock_driver):
        # Configure the mock for body text extraction
        mock_driver.add_human_behavior = Mock()
        mock_body = Mock()
        mock_body.text = "No emails here"
        mock_driver.find_element.return_value = mock_body

        # Configure the mock for mailto links
        mock_driver.find_elements.return_value = []

        # Execute the function
        emails = extract_emails_from_page(mock_driver, "http://anyurl.com")

        # Assert the results
        self.assertEqual(emails, set())

    @patch('selenium.webdriver.remote.webdriver.WebDriver')
    def test_extract_emails_from_page_driver_get_exception(self, mock_driver):
        # Configure the mock to raise an exception
        mock_driver.add_human_behavior = Mock()
        mock_driver.get.side_effect = Exception("Failed to load page")

        # Execute the function
        emails = extract_emails_from_page(mock_driver, "http://anyurl.com")

        # Assert the results
        self.assertEqual(emails, set())

if __name__ == '__main__':
    unittest.main()
