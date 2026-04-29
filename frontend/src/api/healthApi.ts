import { apiRequest, backendBaseUrl } from "./httpClient";
import type { BackendHealthResponse } from "./types";

export function getBackendHealth() {
  return apiRequest<BackendHealthResponse>(
    "/",
    { method: "GET" },
    { baseUrl: backendBaseUrl },
  );
}
