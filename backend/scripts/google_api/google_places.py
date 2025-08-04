import os
import requests
import sqlite3
import time
from geopy.geocoders import Nominatim
from backend.config import Config
from backend.database import insert_lead, update_lead
import logging

from config.utils import extract_base_url

def location_to_latlng(location):
    """
    Convert a location name to latitude and longitude using Nominatim.

    Args:
        location (str): Location name (e.g., "Sarande, Albania").

    Returns:
        str: Latitude,longitude string (e.g., "39.8755,20.0051") or None if not found.
    """
    try:
        geolocator = Nominatim(user_agent="geoapi")
        loc = geolocator.geocode(location)
        if loc:
            logging.info(f"Geocoded {location} to {loc.latitude},{loc.longitude}")
            return f"{loc.latitude},{loc.longitude}"
        else:
            logging.warning(f"Location not found: {location}")
            return None
    except Exception as e:
        logging.error(f"Geocoding failed for {location}: {e}")
        return None

def call_google_places_api_near_search(job_id, location, radius=300, place_type="lodging", max_places=20):
    """
    Fetch places from Google Places API and store results in the leads table.

    Args:
        job_id (str): Unique job ID for tracking.
        location (str): Location name (e.g., "Sarande, Albania").
        radius (int): Search radius in meters (default: 300).
        place_type (str): Google Places type (e.g., "lodging").
        max_places (int): Maximum number of places to fetch (default: 20).

    Returns:
        list: List of place details (name, address, phone, website, place_id).
    """
    # Validate inputs
    if not job_id or not isinstance(job_id, str):
        logging.error("Invalid or missing job_id")
        return []
    if not location or not isinstance(location, str):
        logging.error("Invalid or missing location")
        return []
    if not Config.GOOGLE_API_KEY:
        logging.error("Google API key is missing")
        return []

    api_key = Config.GOOGLE_API_KEY
    coordinates = location_to_latlng(location)
    if not coordinates:
        logging.error(f"Invalid coordinates for location: {location}")
        return []

    # Open a single database connection
    conn = sqlite3.connect(os.path.join(Config.TEMP_PATH, "scraping.db"))
    try:
        cursor = conn.cursor()
        # Nearby Search endpoint
        url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        params = {
            "location": coordinates,
            "radius": radius,
            "type": place_type,
            "key": api_key
        }
        response = requests.get(url, params=params)
        response.raise_for_status()
        places = response.json().get("results", [])
        logging.info(f"Found {len(places)} places for location {location}")

        results = []
        count = 0
        for place in places:
            if count >= max_places:
                break
            place_id = place.get("place_id")
            if not place_id:
                logging.warning(f"Skipping place with missing place_id in {location}")
                continue

            # Fetch place details
            details_url = "https://maps.googleapis.com/maps/api/place/details/json"
            details_params = {
                "place_id": place_id,
                "fields": "name,formatted_address,international_phone_number,website",
                "key": api_key
            }
            details_response = requests.get(details_url, params=details_params)
            logging.info(f"Places Response: {details_response}")
            time.sleep(0.1)  # Respect API rate limits
            details_response.raise_for_status()
            details_data = details_response.json()
            
            # Check API response status
            if details_data.get("status") != "OK":
                logging.error(f"Place Details API failed for place_id {place_id}: {details_data.get('error_message', 'Unknown error')}")
                continue

            details = details_data.get("result", {})
            lead_data = {
                "job_id": job_id,
                "place_id": place_id,
                "location": location,
                "name": details.get("name"),
                "address": details.get("formatted_address"),
                "phone": details.get("international_phone_number"),
                "website": details.get("website")
            }
            logging.info(f"Lead Data: {lead_data}")
            results.append(lead_data)

            # Check if lead exists
            cursor.execute("SELECT lead_id FROM leads WHERE place_id = ?", (place_id,))
            existing_lead = cursor.fetchone()
            logging.info(f"Existing Lead: {existing_lead}")
            if existing_lead:
                # Update existing lead
                update_lead(
                    conn=conn,
                    job_id=job_id,
                    place_id=place_id,
                    location=lead_data["location"],
                    name=lead_data["name"],
                    address=lead_data["address"],
                    phone=lead_data["phone"],
                    website=lead_data["website"]
                )
                logging.info(f"Updated existing lead for place {lead_data['name']} (job_id: {job_id})")
            else:
                # Insert new lead
                insert_lead(
                    conn=conn,
                    job_id=job_id,
                    place_id=place_id,
                    location=lead_data["location"],
                    name=lead_data["name"],
                    address=lead_data["address"],
                    phone=lead_data["phone"],
                    website=lead_data["website"]
                )
                logging.info(f"Stored lead for place {lead_data['name']} (job_id: {job_id})")
            count += 1

        conn.commit()
        return results

    except requests.RequestException as e:
        logging.error(f"Google Places API call failed for job {job_id}: {e}")
        return []
    except sqlite3.Error as e:
        logging.error(f"Database error for job {job_id}: {e}")
        return []
    except Exception as e:
        logging.error(f"Unexpected error for job {job_id}: {e}")
        return []
    finally:
        if conn:
            conn.close()

def call_google_places_api(job_id, location, radius=300, place_type="lodging", max_places=20):
    """
    Fetch places from Google Places Text Search (New) API and store results in the leads table.

    Args:
        job_id (str): Unique job ID for tracking.
        location (str): Location name (e.g., "Sarande, Albania").
        radius (int): Ignored (kept for compatibility; uses viewport instead).
        place_type (str): Google Places type (e.g., "lodging").
        max_places (int): Maximum number of places to fetch (default: 20).

    Returns:
        list: List of place details (name, address, phone, website, place_id).
    """
    # Validate inputs
    if not job_id or not isinstance(job_id, str):
        logging.error("Invalid or missing job_id")
        return []
    if not location or not isinstance(location, str):
        logging.error("Invalid or missing location")
        return []
    if not Config.GOOGLE_API_KEY:
        logging.error("Google API key is missing")
        return []

    api_key = Config.GOOGLE_API_KEY
    text_query = f"{place_type} in {location}"

    # Open a single database connection
    conn = sqlite3.connect(os.path.join(Config.TEMP_PATH, "scraping.db"))
    try:
        cursor = conn.cursor()
        # Text Search (New) endpoint
        url = "https://places.googleapis.com/v1/places:searchText"
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.internationalPhoneNumber,places.websiteUri,places.types,nextPageToken"
        }

        results = []
        count = 0
        next_page_token = None

        while count < max_places:
            body = {
                "textQuery": text_query,
                "pageSize": min(20, max_places - count),  # Max 20 per page
                "includedType": place_type
            }
            if next_page_token:
                body["pageToken"] = next_page_token

            response = requests.post(url, json=body, headers=headers)
            logging.info(f"Text Search Response: {response.status_code}")
            response.raise_for_status()
            data = response.json()
            places = data.get("places", [])
            logging.info(f"Found {len(places)} places for query: {text_query}")

            for place in places:
                if count >= max_places:
                    break
                place_id = place.get("id")
                if not place_id:
                    logging.warning(f"Skipping place with missing place_id in {location}")
                    continue
                # Parsing and filtering website
                website = extract_base_url(place.get("websiteUri"))
                
                lead_data = {
                    "job_id": job_id,
                    "place_id": place_id,
                    "location": f"{place_type}:{location}",
                    "name": place.get("displayName", {}).get("text"),
                    "address": place.get("formattedAddress"),
                    "phone": place.get("internationalPhoneNumber"),
                    "website": website
                }
                logging.info(f"Lead Data: {lead_data}")
                results.append(lead_data)

                # Check if lead exists
                logging.info("Before Select")
                cursor.execute("SELECT lead_id FROM leads WHERE place_id = ?", (place_id,))
                logging.info("After Select")
                existing_lead = cursor.fetchone()
                logging.info(f"Existing Lead: {existing_lead}")

                if existing_lead:
                    # Update existing lead
                    update_lead(
                        conn=conn,
                        job_id=job_id,
                        place_id=place_id,
                        location=lead_data["location"],
                        name=lead_data["name"],
                        address=lead_data["address"],
                        phone=lead_data["phone"],
                        website=lead_data["website"]
                    )
                    logging.info(f"Updated existing lead for place {lead_data['name']} (job_id: {job_id})")
                else:
                    # Insert new lead
                    insert_lead(
                        conn=conn,
                        job_id=job_id,
                        place_id=place_id,
                        location=lead_data["location"],
                        name=lead_data["name"],
                        address=lead_data["address"],
                        phone=lead_data["phone"],
                        website=lead_data["website"]
                    )
                    logging.info(f"Stored lead for place {lead_data['name']} (job_id: {job_id})")
                count += 1

            next_page_token = data.get("nextPageToken")
            logging.info(f"PageToken: {next_page_token}")
            if not next_page_token or count >= max_places:
                break
            time.sleep(2)  # Wait for nextPageToken to become valid

        conn.commit()
        return results

    except requests.RequestException as e:
        logging.error(f"Google Places API call failed for job {job_id}: {e}")
        return []
    except sqlite3.Error as e:
        logging.error(f"Database error for job {job_id}: {e}")
        return []
    except Exception as e:
        logging.error(f"Unexpected error for job {job_id}: {e}")
        return []
    finally:
        if conn:
            conn.close()