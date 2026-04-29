import type { ApiErrorPayload } from "./types";

export class ApiError extends Error {
  readonly status: number;
  readonly payload: ApiErrorPayload | unknown;

  constructor(message: string, status: number, payload: ApiErrorPayload | unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

export type ApiClientOptions = {
  baseUrl?: string;
  fetcher?: typeof fetch;
};

const DEFAULT_API_BASE_URL = "/api";
const HEALTH_BASE_URL = "";

export const apiBaseUrl =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ?? DEFAULT_API_BASE_URL;

export const backendBaseUrl =
  import.meta.env.VITE_BACKEND_BASE_URL?.replace(/\/$/, "") ?? HEALTH_BASE_URL;

async function parseResponse(response: Response) {
  const contentType = response.headers.get("content-type") ?? "";

  if (contentType.includes("application/json")) {
    return response.json();
  }

  return response.text();
}

export async function apiRequest<TResponse>(
  path: string,
  init: RequestInit = {},
  options: ApiClientOptions = {},
): Promise<TResponse> {
  const baseUrl = options.baseUrl ?? apiBaseUrl;
  const fetcher = options.fetcher ?? fetch;
  const response = await fetcher(`${baseUrl}${path}`, {
    ...init,
    headers: {
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...init.headers,
    },
  });

  const payload = await parseResponse(response);

  if (!response.ok) {
    const message =
      typeof payload === "object" &&
      payload !== null &&
      "error" in payload &&
      typeof payload.error === "string"
        ? payload.error
        : `Request failed with status ${response.status}`;

    throw new ApiError(message, response.status, payload);
  }

  return payload as TResponse;
}

export async function downloadRequest(
  path: string,
  init: RequestInit = {},
  options: ApiClientOptions = {},
): Promise<Blob> {
  const baseUrl = options.baseUrl ?? apiBaseUrl;
  const fetcher = options.fetcher ?? fetch;
  const response = await fetcher(`${baseUrl}${path}`, init);

  if (!response.ok) {
    const payload = await parseResponse(response);
    const message =
      typeof payload === "object" &&
      payload !== null &&
      "error" in payload &&
      typeof payload.error === "string"
        ? payload.error
        : `Download failed with status ${response.status}`;

    throw new ApiError(message, response.status, payload);
  }

  return response.blob();
}
