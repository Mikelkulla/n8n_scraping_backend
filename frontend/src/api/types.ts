export type JobStatus = "running" | "completed" | "failed" | "stopped";

export type JobStepId = "email_scrape" | "google_maps_scrape" | "leads_email_scrape";

export type ApiErrorPayload = {
  error: string;
  job_id?: string;
};

export type BackendHealthResponse = {
  status: "ok";
  message: string;
};

export type WebsiteEmailScrapeRequest = {
  url: string;
  max_pages?: number;
  use_tor?: boolean;
  headless?: boolean;
  sitemap_limit?: number;
};

export type WebsiteEmailScrapeResponse = {
  job_id: string;
  input: string;
  emails: string[];
  status: "completed";
};

export type GoogleMapsScrapeRequest = {
  location: string;
  radius?: number;
  place_type?: string;
  max_places?: number;
};

export type Lead = {
  lead_id?: number;
  execution_id?: number;
  place_id?: string;
  job_id?: string;
  location?: string | null;
  name?: string | null;
  address?: string | null;
  phone?: string | null;
  website?: string | null;
  emails?: string | null;
  status?: string | null;
  lead_flag?: string | null;
  lead_status?: string | null;
  notes?: string | null;
  website_summary?: string | null;
  summary_source_url?: string | null;
  summary_status?: "captured" | "empty" | "failed" | string | null;
  summary_updated_at?: string | null;
  created_at?: string;
  updated_at?: string;
};

export type LeadEmail = {
  email_id: number;
  lead_id: number;
  email: string;
  category: string;
  status: string;
  is_primary: boolean | number;
  notes?: string | null;
  created_at: string;
  updated_at: string;
};

export type GoogleMapsScrapeResponse = {
  job_id: string;
  input: string;
  status: "completed";
  leads: Lead[];
};

export type LeadsEmailScrapeRequest = {
  max_pages?: number;
  use_tor?: boolean;
  headless?: boolean;
};

export type LeadsEmailScrapeStartedResponse = {
  job_id: string;
  status: "started";
  total_leads: number;
};

export type EmptyLeadsResponse = {
  message: string;
  count: 0;
};

export type LeadsEmailScrapeResponse = LeadsEmailScrapeStartedResponse | EmptyLeadsResponse;

export type JobProgressResponse = {
  job_id: string;
  step_id: JobStepId;
  input: string;
  max_pages: number | null;
  use_tor: boolean | null;
  headless: boolean | null;
  current_row: number | null;
  total_rows: number | null;
  status: JobStatus;
  error_message: string | null;
};

export type StopJobResponse = {
  job_id: string;
  status: "stopped";
};

export type JobExecution = {
  execution_id: number;
  job_id: string;
  step_id: JobStepId;
  input: string;
  max_pages: number | null;
  use_tor: boolean | null;
  headless: boolean | null;
  status: JobStatus;
  current_row: number | null;
  total_rows: number | null;
  created_at: string;
  updated_at: string;
  error_message: string | null;
  stop_call: boolean | number;
};

export type ListJobsParams = {
  status?: JobStatus;
  step_id?: JobStepId;
  limit?: number;
};

export type ListJobsResponse = {
  count: number;
  jobs: JobExecution[];
};

export type SummaryResponse = {
  leads: {
    total: number;
    with_website: number;
    with_email: number;
    pending_enrichment: number;
    scraped: number;
    failed: number;
    skipped: number;
  };
  jobs: {
    total: number;
    running: number;
    completed: number;
    failed: number;
    stopped: number;
  };
};

export type ExportLeadsJsonResponse = {
  count: number;
  leads: Lead[];
};

export type EmptyExportResponse = {
  message: string;
  count: 0;
};

export type ExportLeadsResponse = ExportLeadsJsonResponse | EmptyExportResponse;

export type ListLeadsParams = {
  status?: string;
  job_id?: string;
  has_email?: boolean;
  has_website?: boolean;
  lead_flag?: string;
  lead_status?: string;
};

export type ListLeadsResponse = {
  count: number;
  leads: Lead[];
};

export type UpdateLeadRequest = {
  website?: string;
  emails?: string | string[];
  status?: string;
  lead_flag?: string;
  lead_status?: string;
  notes?: string;
  website_summary?: string;
};

export type UpdateLeadResponse = {
  lead: Lead;
};

export type ListLeadEmailsResponse = {
  count: number;
  emails: LeadEmail[];
};

export type AddLeadEmailRequest = {
  email: string;
  category?: string;
  status?: string;
  is_primary?: boolean;
  notes?: string;
};

export type LeadEmailResponse = {
  email: LeadEmail;
};

export type UpdateLeadEmailRequest = {
  category?: string;
  status?: string;
  is_primary?: boolean;
  notes?: string;
};

export type DeleteLeadEmailResponse = {
  deleted: {
    email_id: number;
    lead_id: number;
  };
};
