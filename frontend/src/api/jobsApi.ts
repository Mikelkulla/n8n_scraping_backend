import { apiRequest } from "./httpClient";
import type { JobProgressResponse, StopJobResponse } from "./types";

export function getJobProgress(jobId: string) {
  return apiRequest<JobProgressResponse>(`/progress/${encodeURIComponent(jobId)}`);
}

export function stopJob(jobId: string) {
  return apiRequest<StopJobResponse>(`/stop/${encodeURIComponent(jobId)}`, {
    method: "POST",
  });
}
