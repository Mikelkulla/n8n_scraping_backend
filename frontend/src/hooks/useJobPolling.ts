import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getJobProgress, listJobs, stopJob } from "../api";
import type { JobProgressResponse, ListJobsParams } from "../api";
import { queryKeys } from "./queryKeys";

const TERMINAL_STATUSES = new Set(["completed", "failed", "stopped"]);

export function isTerminalJob(progress?: JobProgressResponse) {
  return progress ? TERMINAL_STATUSES.has(progress.status) : false;
}

export function useJobPolling(jobId?: string) {
  return useQuery({
    queryKey: queryKeys.jobProgress(jobId ?? ""),
    queryFn: () => getJobProgress(jobId ?? ""),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const progress = query.state.data;
      return isTerminalJob(progress) ? false : 3_000;
    },
  });
}

export function useJobs(params: ListJobsParams = {}) {
  return useQuery({
    queryKey: queryKeys.jobs(params),
    queryFn: () => listJobs(params),
    refetchInterval: 10_000,
  });
}

export function useStopJob() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: stopJob,
    onSuccess: (_, jobId) => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.jobProgress(jobId),
      });
      void queryClient.invalidateQueries({
        queryKey: ["jobs"],
      });
    },
  });
}
