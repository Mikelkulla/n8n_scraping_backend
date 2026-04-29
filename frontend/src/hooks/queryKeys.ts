export const queryKeys = {
  backendHealth: ["backend-health"] as const,
  summary: ["summary"] as const,
  jobs: (params: Record<string, unknown>) => ["jobs", params] as const,
  jobProgress: (jobId: string) => ["job-progress", jobId] as const,
  leads: (params: Record<string, unknown>) => ["leads", params] as const,
  exportLeads: ["export-leads"] as const,
};
