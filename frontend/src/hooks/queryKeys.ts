export const queryKeys = {
  backendHealth: ["backend-health"] as const,
  jobProgress: (jobId: string) => ["job-progress", jobId] as const,
  exportLeads: ["export-leads"] as const,
};
