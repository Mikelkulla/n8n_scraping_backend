from unittest.mock import MagicMock, call, patch

from backend.scripts.scraping.scrape_for_email import EmailScraper


def _manager_with_driver(driver_name):
    manager = MagicMock()
    driver = MagicMock(name=driver_name)
    manager.get_driver.return_value = driver
    manager.driver = driver
    return manager, driver


def test_scrape_pages_reuses_one_driver_for_single_worker():
    scraper = EmailScraper(
        "job1",
        "email_scrape",
        "https://example.com",
        max_pages=3,
        max_threads=1,
    )
    scraper.urls_to_visit = [
        "https://example.com/",
        "https://example.com/about",
        "https://example.com/contact",
    ]
    scraper.total_urls = 3
    manager, driver = _manager_with_driver("worker-driver")

    with patch("backend.scripts.scraping.scrape_for_email.WebDriverManager", return_value=manager) as manager_class:
        with patch("backend.scripts.scraping.scrape_for_email.scrape_page", return_value={"hello@realbusiness.co"}) as scrape_page:
            with patch("backend.scripts.scraping.scrape_for_email.write_progress"):
                with patch("backend.scripts.scraping.scrape_for_email.check_stop_signal", return_value=False):
                    scraper._scrape_pages()

    assert manager_class.call_count == 1
    assert scrape_page.call_args_list == [
        call(driver, "https://example.com/"),
        call(driver, "https://example.com/about"),
        call(driver, "https://example.com/contact"),
    ]
    assert driver.delete_all_cookies.call_count == 3
    assert driver.execute_script.call_count == 3
    manager.close.assert_called_once()
    assert scraper.progress_counter == 3
    assert scraper.all_emails == {"hello@realbusiness.co"}


def test_scrape_pages_caps_worker_drivers_to_max_threads():
    scraper = EmailScraper(
        "job1",
        "email_scrape",
        "https://example.com",
        max_pages=30,
        max_threads=5,
    )
    scraper.urls_to_visit = [f"https://example.com/page-{index}" for index in range(30)]
    scraper.total_urls = 30
    managers = []

    def build_manager(*args, **kwargs):
        manager, _driver = _manager_with_driver(f"worker-driver-{len(managers)}")
        managers.append(manager)
        return manager

    with patch("backend.scripts.scraping.scrape_for_email.WebDriverManager", side_effect=build_manager):
        with patch("backend.scripts.scraping.scrape_for_email.scrape_page", return_value=set()) as scrape_page:
            with patch("backend.scripts.scraping.scrape_for_email.write_progress"):
                with patch("backend.scripts.scraping.scrape_for_email.check_stop_signal", return_value=False):
                    scraper._scrape_pages()

    assert len(managers) == 5
    assert scrape_page.call_count == 30
    for manager in managers:
        manager.close.assert_called_once()


def test_scrape_pages_stop_signal_prevents_new_url_claims():
    scraper = EmailScraper(
        "job1",
        "email_scrape",
        "https://example.com",
        max_pages=3,
        max_threads=1,
    )
    scraper.urls_to_visit = [
        "https://example.com/",
        "https://example.com/about",
        "https://example.com/contact",
    ]
    scraper.total_urls = 3
    manager, _driver = _manager_with_driver("worker-driver")

    with patch("backend.scripts.scraping.scrape_for_email.WebDriverManager", return_value=manager):
        with patch("backend.scripts.scraping.scrape_for_email.scrape_page", return_value=set()) as scrape_page:
            with patch("backend.scripts.scraping.scrape_for_email.write_progress") as write_progress:
                with patch(
                    "backend.scripts.scraping.scrape_for_email.check_stop_signal",
                    side_effect=lambda *_args, **_kwargs: scraper.progress_counter >= 1,
                ):
                    scraper._scrape_pages()

    assert scrape_page.call_count == 1
    assert any(call_args.kwargs.get("status") == "stopped" for call_args in write_progress.call_args_list)
    manager.close.assert_called_once()


def test_scrape_pages_failed_worker_driver_creation_does_not_stop_other_workers():
    scraper = EmailScraper(
        "job1",
        "email_scrape",
        "https://example.com",
        max_pages=2,
        max_threads=2,
    )
    scraper.urls_to_visit = [
        "https://example.com/",
        "https://example.com/contact",
    ]
    scraper.total_urls = 2
    good_manager, _driver = _manager_with_driver("good-driver")

    with patch(
        "backend.scripts.scraping.scrape_for_email.WebDriverManager",
        side_effect=[RuntimeError("driver startup failed"), good_manager],
    ) as manager_class:
        with patch("backend.scripts.scraping.scrape_for_email.scrape_page", return_value=set()) as scrape_page:
            with patch("backend.scripts.scraping.scrape_for_email.write_progress"):
                with patch("backend.scripts.scraping.scrape_for_email.check_stop_signal", return_value=False):
                    scraper._scrape_pages()

    assert manager_class.call_count == 2
    assert scrape_page.call_count == 2
    good_manager.close.assert_called_once()


def test_scrape_pages_empty_driver_is_closed_and_other_workers_continue():
    scraper = EmailScraper(
        "job1",
        "email_scrape",
        "https://example.com",
        max_pages=2,
        max_threads=2,
    )
    scraper.urls_to_visit = [
        "https://example.com/",
        "https://example.com/contact",
    ]
    scraper.total_urls = 2
    empty_manager = MagicMock()
    empty_manager.get_driver.return_value = None
    good_manager, _driver = _manager_with_driver("good-driver")

    with patch(
        "backend.scripts.scraping.scrape_for_email.WebDriverManager",
        side_effect=[empty_manager, good_manager],
    ):
        with patch("backend.scripts.scraping.scrape_for_email.scrape_page", return_value=set()) as scrape_page:
            with patch("backend.scripts.scraping.scrape_for_email.write_progress"):
                with patch("backend.scripts.scraping.scrape_for_email.check_stop_signal", return_value=False):
                    scraper._scrape_pages()

    assert scrape_page.call_count == 2
    empty_manager.close.assert_called_once()
    good_manager.close.assert_called_once()
