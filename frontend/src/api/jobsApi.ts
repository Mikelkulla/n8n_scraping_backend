import { apiRequest } from "./httpClient";
import type {
  JobProgressResponse,
  ListJobsParams,
  ListJobsResponse,
  StopJobResponse,
} from "./types";

function toQueryString(params: ListJobsParams = {}) {
  const query = new URLSearchParams();

  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined) {
      query.set(key, String(value));
    }
  });

  const serialized = query.toString();
  return serialized ? `?${serialized}` : "";
}

export function listJobs(params: ListJobsParams = {}) {
  return apiRequest<ListJobsResponse>(`/jobs${toQueryString(params)}`);
}

export function getJobProgress(jobId: string) {
  return apiRequest<JobProgressResponse>(`/progress/${encodeURIComponent(jobId)}`);
}

export function stopJob(jobId: string) {
  return apiRequest<StopJobResponse>(`/stop/${encodeURIComponent(jobId)}`, {
    method: "POST",
  });
}
