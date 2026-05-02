import { useMutation } from "@tanstack/react-query";
import {
  scrapeGoogleMaps,
  scrapeLeadsEmails,
  scrapeWebsiteEmails,
} from "../api";

export function useWebsiteEmailScrape() {
  return useMutation({
    mutationFn: scrapeWebsiteEmails,
  });
}

export function useGoogleMapsScrape() {
  return useMutation({
    mutationFn: scrapeGoogleMaps,
  });
}

export function useLeadEmailEnrichment() {
  return useMutation({
    mutationFn: scrapeLeadsEmails,
  });
}
