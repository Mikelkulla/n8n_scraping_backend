# Web Scraping API

## 1. Project Overview

This project provides a powerful, web-based scraping tool designed to automate the collection of contact information from across the web. It features a robust Flask backend that exposes a set of RESTful APIs to perform two primary scraping tasks:

1.  **Email Scraping:** Systematically crawls a given website to discover and collect email addresses.
2.  **Google Maps Scraping:** Searches for businesses on Google Maps based on location and type, then collects their details, including name, address, phone number, and website.

The application is built to handle long-running jobs efficiently. Asynchronous tasks, like Google Maps scraping, are run in the background, allowing users to track their progress and retrieve results at their convenience. A local SQLite database is used to persist all job information and scraped data.

## 2. How it Works

The application is built on a clean and effective architecture:

*   **Flask Backend:** A lightweight Flask server acts as the application's core. It serves a simple frontend and provides a comprehensive API for managing scraping jobs.
*   **Background Jobs:** For time-intensive tasks like Google Maps scraping, the application spawns new threads to run them in the background. This ensures the API remains responsive and can handle multiple jobs concurrently. A global dictionary, `active_jobs`, tracks all running threads.
*   **SQLite Database:** The application uses a local SQLite database (`scraping.db`) to store persistent data:
    *   **Job Progress:** The status and progress of every scraping job are logged in the `job_executions` table, allowing for real-time monitoring.
    *   **Scraped Data:** Contact information and business details collected from Google Maps are stored in the `leads` table.
*   **Intelligent Scraping Logic:**
    *   **Email Scraping:** Uses Selenium to control a web browser, intelligently navigating websites to find email addresses. It can be configured to use the Tor network for enhanced privacy.
    *   **Google Maps Scraping:** Leverages the official Google Places API to find and retrieve detailed information about businesses.
*   **Centralized Configuration:** All application settings, including API keys, file paths, and driver configurations, are managed in a central `Config` class.

## 3. Data Storage

The application uses a SQLite database named `scraping.db`, located in the `backend/temp/` directory. It consists of two main tables:

### `job_executions`

This table tracks the metadata and status of each scraping job.

| Column          | Type      | Description                                                             |
| --------------- | --------- | --------------------------------------------------------------------    |
| `execution_id`  | `INTEGER` | **Primary Key.** A unique identifier for each job execution.            |
| `job_id`        | `TEXT`    | A unique ID (UUID) for the job, used for tracking.                      |
| `step_id`       | `TEXT`    | The type of job (e.g., "email_scrape", "google_maps_scrape").           |
| `input`         | `TEXT`    | The main input for the job (e.g., a URL or location).                   |
| `max_pages`     | `INTEGER` | The maximum number of pages to scrape (for email scraping).             |
| `use_tor`       | `BOOLEAN` | A flag indicating whether the job should use the Tor network.           |
| `headless`      | `BOOLEAN` | A flag indicating whether the browser should run in headless mode.      |
| `status`        | `TEXT`    | The current status of the job (e.g., "running", "completed", "failed"). |
| `current_row`   | `INTEGER` | The number of items processed so far.                                   |
| `total_rows`    | `INTEGER` | The total number of items to process.                                   |
| `created_at`    | `TIMESTAMP`| The timestamp when the job was created.                                |
| `updated_at`    | `TIMESTAMP`| The timestamp when the job was last updated.                           |
| `error_message` | `TEXT`    | An error message if the job failed.                                     |
| `stop_call`     | `BOOLEAN` | A flag to signal the job to stop.                                       |

### `leads`

This table stores the business data collected from Google Maps scraping jobs.

| Column       | Type      | Description                                                               |
| ------------ | --------- | ------------------------------------------------------------------------- |
| `lead_id`    | `INTEGER` | **Primary Key.** A unique identifier for each lead.                         |
| `job_id`     | `TEXT`    | **Foreign Key** to `job_executions`, linking the lead to a specific job.    |
| `place_id`   | `TEXT`    | The unique ID of the place from Google Maps, used to prevent duplicates.  |
| `location`   | `TEXT`    | The location that was searched (e.g., "Sarande, Albania").                  |
| `name`       | `TEXT`    | The name of the business.                                                 |
| `address`    | `TEXT`    | The full address of the business.                                         |
| `phone`      | `TEXT`    | The international phone number of the business.                           |
| `website`    | `TEXT`    | The website of the business.                                              |
| `emails`     | `TEXT`    | A comma-separated list of emails found for the business.                  |
| `created_at` | `TIMESTAMP`| The timestamp when the lead was created.                                   |
| `updated_at` | `TIMESTAMP`| The timestamp when the lead was last updated.                             |
| `status`     | `TEXT`     | Status of the lead. (scraped, failed)                                     |

## 4. API Endpoints

The API is exposed under the `/api` prefix.

### Start Email Scraping

*   **URL:** `/api/scrape/website-emails`
*   **Method:** `POST`
*   **Description:** Starts a synchronous job to scrape emails from a given website. The results are returned directly in the response.
*   **Request Body (JSON):**
    *   `url` (string, required): The base URL of the website to scrape.
    *   `max_pages` (integer, optional): The maximum number of pages to visit.
    *   `use_tor` (boolean, optional): Whether to route traffic through the Tor network.
    *   `headless` (boolean, optional): Whether to run the browser in headless mode.
*   **Response:**
    ```json
    {
      "job_id": "a_unique_job_id",
      "input": "https://example.com",
      "emails": ["email1@example.com", "email2@example.com"],
      "status": "completed"
    }
    ```

### Start Google Maps Scraping

*   **URL:** `/api/scrape/google-maps`
*   **Method:** `POST`
*   **Description:** Starts an asynchronous job to find and store leads from Google Maps.
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

### Scrape Emails for Existing Leads

*   **URL:** `/api/scrape/leads-emails`
*   **Method:** `POST`
*   **Description:** Initiates email scraping for all unscraped leads in the database that have a website.
*   **Request Body (JSON):**
    *   `max_pages` (integer, optional): Maximum pages to scrape per website. Default: `30`.
    *   `use_tor` (boolean, optional): Whether to use Tor. Default: `false`.
    *   `headless` (boolean, optional): Whether to run in headless mode. Default: `true`.
*   **Response:** A JSON object summarizing the results for each lead.

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

## 5. Setup and Running

To run this project, follow these steps:

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd <repository-directory>
    ```

2.  **Install dependencies:** The project's dependencies are listed in `requirements.txt`. Install them using pip:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configure Google API Key:** The project uses a Google API key for the Google Maps scraping feature. It is highly recommended to use a `.env` file to manage your API key securely.
    
    Create a file named `.env` in the project's root directory and add your API key to it:
    ```
    GOOGLE_API_KEY='YOUR_API_KEY_HERE'
    ```
    Ensure you have a valid API key with the "Places API" enabled in your Google Cloud project.

4.  **Web Drivers:** The project requires Selenium web drivers (ChromeDriver or GeckoDriver) to be placed in the `config/drivers/` directory. The application will automatically select the correct driver for your operating system.

5.  **Run the application:**
    ```bash
    python backend/app.py
    ```
    The application will start on `http://localhost:5000`.
