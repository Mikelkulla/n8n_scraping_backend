export const queryKeys = {
  backendHealth: ["backend-health"] as const,
  jobProgress: (jobId: string) => ["job-progress", jobId] as const,
  leads: (params: Record<string, unknown>) => ["leads", params] as const,
  exportLeads: ["export-leads"] as const,
};
