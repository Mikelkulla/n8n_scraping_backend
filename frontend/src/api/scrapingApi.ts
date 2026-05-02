import { apiRequest } from "./httpClient";
import type {
  GoogleMapsScrapeRequest,
  GoogleMapsScrapeResponse,
  LeadsEmailScrapeRequest,
  LeadsEmailScrapeResponse,
  WebsiteEmailScrapeRequest,
  WebsiteEmailScrapeResponse,
} from "./types";

export function scrapeWebsiteEmails(payload: WebsiteEmailScrapeRequest) {
  return apiRequest<WebsiteEmailScrapeResponse>("/scrape/website-emails", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function scrapeGoogleMaps(payload: GoogleMapsScrapeRequest) {
  return apiRequest<GoogleMapsScrapeResponse>("/scrape/google-maps", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function scrapeLeadsEmails(payload: LeadsEmailScrapeRequest = {}) {
  return apiRequest<LeadsEmailScrapeResponse>("/scrape/leads-emails", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
