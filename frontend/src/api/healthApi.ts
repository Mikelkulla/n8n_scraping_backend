import { apiRequest, backendBaseUrl } from "./httpClient";
import type { BackendHealthResponse } from "./types";

export function getBackendHealth() {
  return apiRequest<BackendHealthResponse>(
    "/backend-health",
    { method: "GET" },
    { baseUrl: backendBaseUrl },
  );
}
