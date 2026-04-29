import { apiRequest } from "./httpClient";
import type { SummaryResponse } from "./types";

export function getSummary() {
  return apiRequest<SummaryResponse>("/summary");
}
