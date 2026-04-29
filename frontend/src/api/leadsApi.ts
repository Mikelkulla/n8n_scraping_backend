import { downloadRequest, apiRequest } from "./httpClient";
import type { ExportLeadsResponse } from "./types";

export function exportLeadsJson() {
  return apiRequest<ExportLeadsResponse>("/leads/export?format=json");
}

export function downloadLeadsCsv() {
  return downloadRequest("/leads/export");
}
