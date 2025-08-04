# Project Documentation

## 1. Project Overview

This project is a web-based scraping tool designed to automate the collection of contact information. It provides a Flask-based backend with a set of APIs to perform two main tasks:

1.  **Email Scraping:** Scrape a given website to find and collect email addresses.
2.  **Google Maps Scraping:** Search for businesses on Google Maps based on location and type, and collect their details (name, address, phone number, website).

The application is designed to handle long-running scraping tasks by executing them in the background, allowing users to track their progress and retrieve the results when they are ready. It uses a SQLite database to store job information and scraped data.

## 2. How it Works

The application follows a simple yet powerful architecture:

*   **Flask Backend:** A lightweight Flask web server provides the main entry point for the application. It serves a simple frontend (not detailed in this documentation) and exposes a RESTful API for controlling the scraping jobs.

*   **Background Jobs:** When a new scraping job is initiated via the API, the application spawns a new thread to run the task in the background. This ensures that the API remains responsive and can handle multiple jobs concurrently. A dictionary `active_jobs` is used to keep track of the running threads.

*   **SQLite Database:** The application uses a local SQLite database (`scraping.db`) to persist data. This includes:
    *   **Job Progress:** The status and progress of each scraping job are stored in the `job_executions` table. This allows users to monitor the state of their jobs.
    *   **Scraped Data:** The data collected from Google Maps is stored in the `leads` table.

*   **Scraping Logic:** The core scraping functionality is implemented in separate scripts:
    *   **Email Scraping:** Uses Selenium to control a web browser (Chrome) and scrape websites for email addresses. It can be configured to use the Tor network for anonymity.
    *   **Google Maps Scraping:** Uses the official Google Places API to search for businesses and retrieve their details.

*   **Configuration:** The application's settings are managed in a central `Config` class, which includes API keys, file paths, and driver configurations.

## 3. Data Storage

The application uses a SQLite database named `scraping.db`, which is created in the `backend/temp/` directory. The database consists of two main tables:

### `job_executions`

This table tracks the status and metadata of each scraping job.

| Column          | Type      | Description                                                                                             |
| --------------- | --------- | ------------------------------------------------------------------------------------------------------- |
| `execution_id`  | `INTEGER` | **Primary Key.** A unique identifier for each execution.                                                |
| `job_id`        | `TEXT`    | A unique ID (UUID) for the job, used to track it across the system.                                     |
| `step_id`       | `TEXT`    | The type of job (e.g., "email_scrape", "google_maps_scrape").                                           |
| `input`         | `TEXT`    | The main input for the job (e.g., the URL or location to scrape).                                       |
| `max_pages`     | `INTEGER` | The maximum number of pages to scrape (for email scraping).                                             |
| `use_tor`       | `BOOLEAN` | Whether the job should use the Tor network.                                                             |
| `headless`      | `BOOLEAN` | Whether the browser should run in headless mode.                                                        |
| `status`        | `TEXT`    | The current status of the job (e.g., "running", "completed", "failed", "stopped").                      |
| `current_row`   | `INTEGER` | The number of items processed so far.                                                                   |
| `total_rows`    | `INTEGER` | The total number of items to process.                                                                   |
| `created_at`    | `TIMESTAMP`| The timestamp when the job was created.                                                                |
| `updated_at`    | `TIMESTAMP`| The timestamp when the job was last updated.                                                           |
| `error_message` | `TEXT`    | Any error message if the job failed.                                                                    |
| `stop_call`     | `BOOLEAN` | A flag to signal the job to stop.                                                                       |

### `leads`

This table stores the data collected from the Google Maps scraping jobs.

| Column       | Type      | Description                                                               |
| ------------ | --------- | ------------------------------------------------------------------------- |
| `lead_id`    | `INTEGER` | **Primary Key.** A unique identifier for each lead.                         |
| `job_id`     | `TEXT`    | **Foreign Key** to `job_executions`. Links the lead to a specific job.      |
| `place_id`   | `TEXT`    | The unique ID of the place from Google Maps. Used to prevent duplicates.  |
| `location`   | `TEXT`    | The location that was searched (e.g., "Sarande, Albania").                  |
| `name`       | `TEXT`    | The name of the business.                                                 |
| `address`    | `TEXT`    | The full address of the business.                                         |
| `phone`      | `TEXT`    | The international phone number of the business.                           |
| `website`    | `TEXT`    | The website of the business.                                              |
| `emails`     | `TEXT`    | A comma-separated list of emails found for the business (currently not populated by the Google Maps scraper). |
| `created_at` | `TIMESTAMP`| The timestamp when the lead was created.                                   |

## 4. API Endpoints

The API is exposed under the `/api` prefix.

### Start Email Scraping

*   **URL:** `/api/scrape/website-emails`
*   **Method:** `POST`
*   **Description:** Starts a new job to scrape emails from a given website.
*   **Request Body (JSON):**
    *   `url` (string, required): The base URL of the website to scrape.
    *   `max_pages` (integer, optional): The maximum number of pages to visit.
    *   `use_tor` (boolean, optional): Whether to route traffic through the Tor network.
    *   `headless` (boolean, optional): Whether to run the browser in headless mode.
*   **Response:**
    ```json
    {
      "job_id": "a_unique_job_id",
      "status": "started",
      "input": "https://example.com"
    }
    ```

### Start Google Maps Scraping

*   **URL:** `/api/scrape/google-maps`
*   **Method:** `POST`
*   **Description:** Starts a new job to find and store leads from Google Maps.
*   **Request Body (JSON):**
    *   `location` (string, required): The location to search for (e.g., "Sarande, Albania").
    *   `radius` (integer, optional): The search radius in meters. Default: `300`.
    *   `place_type` (string, optional): The type of place to search for (e.g., "lodging", "restaurant"). Default: `"lodging"`.
    *   `max_places` (integer, optional): The maximum number of places to retrieve. Default: `20`.
*   **Response:**
    ```json
    {
      "job_id": "a_unique_job_id",
      "status": "started",
      "input": "Sarande, Albania"
    }
    ```

### Get Job Progress

*   **URL:** `/api/progress/<job_id>`
*   **Method:** `GET`
*   **Description:** Retrieves the progress and status of a specific scraping job.
*   **URL Parameters:**
    *   `job_id` (string, required): The ID of the job to check.
*   **Response:**
    ```json
    {
      "job_id": "a_unique_job_id",
      "step_id": "email_scrape",
      "input": "https://example.com",
      "max_pages": 10,
      "use_tor": false,
      "headless": true,
      "current_row": 5,
      "total_rows": 10,
      "status": "running",
      "error_message": null
    }
    ```

### Stop a Scraping Job

*   **URL:** `/api/stop/<job_id>`
*   **Method:** `POST`
*   **Description:** Stops a currently running scraping job.
*   **URL Parameters:**
    *   `job_id` (string, required): The ID of the job to stop.
*   **Response:**
    ```json
    {
      "job_id": "a_unique_job_id",
      "status": "stopped"
    }
    ```

## 5. Key Functions

*   `scrape_emails(job_id, step_id, base_url, ...)`: Orchestrates the email scraping process. It discovers URLs from the website's sitemap, sorts them by the likelihood of containing contact information, and then iterates through them to find emails.

*   `call_google_places_api(job_id, location, ...)`: Handles the interaction with the Google Places API. It first converts the location name to coordinates, then performs a "Nearby Search," and finally fetches the details for each place found.

*   `sort_urls_by_email_likelihood(urls)`: A helper function that scores and sorts URLs based on keywords (e.g., "contact", "about") and length. This smart sorting makes the email scraping process more efficient.

*   `database.py` functions: The functions in this file (`init_db`, `insert_job_execution`, `get_job_execution`, `insert_lead`, etc.) provide a clean interface for interacting with the SQLite database.

## 6. Code Flow

Here is a typical workflow for an email scraping job:

1.  **API Request:** A user sends a `POST` request to `/api/scrape/website-emails` with a URL to scrape.
2.  **Job Creation:** The Flask application receives the request, generates a unique `job_id`, and creates a new record in the `job_executions` table with the status "running".
3.  **Background Thread:** The application starts a new thread that calls the `scrape_emails` function, passing the `job_id` and other parameters.
4.  **Scraping:** The `scrape_emails` function initializes a Selenium WebDriver, discovers URLs from the website, and starts scraping them one by one.
5.  **Progress Updates:** After each page is scraped, the function calls `write_progress` to update the `current_row` in the `job_executions` table.
6.  **User Monitoring:** While the job is running, the user can send `GET` requests to `/api/progress/<job_id>` to check its status.
7.  **Job Completion:** Once the scraping is finished, the job's status is updated to "completed", and the collected emails are saved to a JSON file in the `backend/temp/` directory.
8.  **Stopping a Job:** If the user sends a `POST` request to `/api/stop/<job_id>`, the application creates a stop signal file. The `scrape_emails` function checks for this file in its loop and will exit gracefully if it's found.

## 7. Setup and Running

To run this project, you will need to follow these steps:

1.  **Clone the repository.**
2.  **Install dependencies:** The project's dependencies are not listed in `requirements.txt`. You will need to manually install the required libraries, such as `Flask`, `requests`, `geopy`, and `selenium`.
    ```bash
    pip install Flask requests geopy selenium
    ```
3.  **Configure Google API Key:** The project uses a Google API key for the Google Maps scraping feature. You will need to have a valid API key with the "Places API" enabled. The key is hardcoded in `backend/config.py`:
    ```python
    class Config:
        GOOGLE_API_KEY = 'YOUR_API_KEY_HERE'
    ```
    **Note:** It is strongly recommended to use an environment variable for the API key instead of hardcoding it.

4.  **Web Drivers:** The project requires Selenium web drivers (ChromeDriver or GeckoDriver) to be placed in the `config/drivers/` directory. The `Config` class will automatically select the correct driver based on your operating system.

5.  **Run the application:**
    ```bash
    python backend/app.py
    ```
    The application will start on `http://localhost:5000`.
