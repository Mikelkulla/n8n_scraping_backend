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
  created_at?: string;
  updated_at?: string;
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
};

export type ListLeadsResponse = {
  count: number;
  leads: Lead[];
};
