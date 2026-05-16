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
  campaign_count?: number;
  campaign_names?: string[];
  campaign_memberships?: CampaignMembership[];
  discovery_count?: number;
  last_discovered_at?: string | null;
  last_discovery_job_id?: string | null;
  created_at?: string;
  updated_at?: string;
};

export type CampaignMembership = {
  campaign_id: number;
  campaign_name: string;
  stage: string;
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
  status: "stopping" | "stopped";
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
  has_phone?: boolean;
  lead_flag?: string;
  lead_status?: string;
  business_type?: string;
  search_location?: string;
};

export type ListLeadsResponse = {
  count: number;
  leads: Lead[];
};

export type LeadFilterOptionsResponse = {
  business_types: Array<{
    value: string;
    count: number;
  }>;
  search_locations: Array<{
    value: string;
    count: number;
  }>;
  pairs: Array<{
    business_type: string;
    search_location: string;
    count: number;
  }>;
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

export type CampaignStatus = "draft" | "active" | "paused" | "completed" | "archived" | string;

export type Campaign = {
  campaign_id: number;
  name: string;
  business_type?: string | null;
  search_location?: string | null;
  filters_json?: string | null;
  status: CampaignStatus;
  notes?: string | null;
  total_leads: number;
  review: number;
  ready_for_email: number;
  drafted: number;
  approved: number;
  contacted: number;
  replied?: number;
  closed?: number;
  skipped?: number;
  do_not_contact?: number;
  created_at: string;
  updated_at: string;
};

export type CreateCampaignRequest = {
  name: string;
  filters: ListLeadsParams;
  notes?: string;
};

export type CampaignResponse = {
  campaign: Campaign;
};

export type CreateCampaignResponse = CampaignResponse & {
  added_leads: number;
  skipped_existing: number;
};

export type ListCampaignsResponse = {
  count: number;
  campaigns: Campaign[];
};

export type CampaignLead = {
  campaign_lead_id: number;
  campaign_id: number;
  lead_id: number;
  stage: string;
  priority?: string | null;
  email_draft?: string | null;
  final_email?: string | null;
  campaign_notes?: string | null;
  contacted_at?: string | null;
  gmail_draft_id?: string | null;
  gmail_message_id?: string | null;
  gmail_draft_status?: string | null;
  gmail_drafted_at?: string | null;
  gmail_error?: string | null;
  created_at: string;
  updated_at: string;
  execution_id?: number;
  place_id?: string;
  location?: string | null;
  name?: string | null;
  address?: string | null;
  phone?: string | null;
  website?: string | null;
  emails?: string | null;
  primary_email?: string | null;
  lead_scrape_status?: string | null;
  lead_flag?: string | null;
  lead_status?: string | null;
  notes?: string | null;
  website_summary?: string | null;
  summary_source_url?: string | null;
  summary_status?: string | null;
  summary_updated_at?: string | null;
  job_id?: string;
  campaign_name?: string;
  business_type?: string | null;
  search_location?: string | null;
};

export type ListCampaignLeadsParams = {
  stage?: string;
  lead_flag?: string;
  lead_status?: string;
  has_email?: boolean;
  has_website?: boolean;
  search?: string;
};

export type ListCampaignLeadsResponse = {
  count: number;
  leads: CampaignLead[];
};

export type UpdateCampaignRequest = {
  name?: string;
  status?: string;
  notes?: string;
};

export type UpdateCampaignLeadRequest = {
  stage?: string;
  priority?: string;
  email_draft?: string;
  final_email?: string;
  campaign_notes?: string;
  contacted_at?: string;
};

export type CampaignLeadResponse = {
  campaign_lead: CampaignLead;
};

export type GmailStatus = {
  configured: boolean;
  authenticated: boolean;
  account_email?: string | null;
  scopes: string[];
  client_secret_path: string;
  token_path: string;
};

export type GmailStatusResponse = {
  gmail: GmailStatus;
};

export type GmailAuthStartRequest = {
  redirect_uri?: string;
};

export type GmailAuthStartResponse = {
  authorization_url: string;
  state: string;
  redirect_uri: string;
};

export type AiEmailProvider = "openai" | "anthropic";

export type EmailSettings = {
  provider: AiEmailProvider | string;
  model: string;
  system_prompt: string;
  user_prompt: string;
  api_key_configured: boolean;
};

export type EmailSettingsResponse = {
  settings: EmailSettings;
};

export type UpdateEmailSettingsRequest = {
  provider?: AiEmailProvider;
  model?: string;
  system_prompt?: string;
  user_prompt?: string;
};

export type AppSettings = {
  log_level: "DEBUG" | "INFO" | "WARNING" | "ERROR" | "CRITICAL" | string;
  scraper_max_pages: number;
  scraper_sitemap_limit: number;
  scraper_headless: boolean;
  scraper_use_tor: boolean;
  scraper_max_threads: number;
  places_place_type: string;
  places_max_places: number;
  places_radius: number;
};

export type AppSettingsEnvironment = {
  google_api_key_configured: boolean;
  openai_api_key_configured: boolean;
  anthropic_api_key_configured: boolean;
  tor_path?: string | null;
  tor_configured: boolean;
  chromedriver_path?: string | null;
  chromedriver_configured: boolean;
  geckodriver_path?: string | null;
  geckodriver_configured: boolean;
  log_path: string;
  temp_path: string;
};

export type AppSettingsResponse = {
  settings: AppSettings;
  environment: AppSettingsEnvironment;
};

export type UpdateAppSettingsRequest = Partial<AppSettings>;

export type BusinessTypeEmailRule = {
  business_type: string;
  business_description?: string | null;
  pain_point?: string | null;
  offer_angle?: string | null;
  extra_instructions?: string | null;
  created_at?: string;
  updated_at?: string;
};

export type BusinessTypeEmailRulesResponse = {
  count: number;
  rules: BusinessTypeEmailRule[];
};

export type BusinessTypeEmailRuleResponse = {
  rule: BusinessTypeEmailRule;
};

export type UpdateBusinessTypeEmailRuleRequest = {
  business_description?: string;
  pain_point?: string;
  offer_angle?: string;
  extra_instructions?: string;
};

export type GenerateCampaignEmailsRequest = {
  stage?: string;
  search?: string;
  limit?: number;
};

export type GenerateCampaignEmailsResponse = {
  generated_count: number;
  skipped_count: number;
  error_count: number;
  generated: CampaignLead[];
  skipped: Array<{ campaign_lead_id?: number; reason: string }>;
  errors: Array<{ campaign_lead_id?: number; error: string }>;
};

export type EmailCategoryRule = {
  rule_id: number;
  pattern: string;
  match_type: "local_part_exact" | string;
  category: string;
  is_active: boolean | number;
  created_at: string;
  updated_at: string;
};

export type ListEmailCategoryRulesResponse = {
  count: number;
  categories: string[];
  rules: EmailCategoryRule[];
};

export type EmailCategoryRuleResponse = {
  rule: EmailCategoryRule;
};

export type UpdateEmailCategoryRuleRequest = {
  category: string;
  is_active?: boolean;
};

export type UnknownEmailLocalPart = {
  local_part: string;
  count: number;
  example_email: string;
};

export type UnknownEmailLocalPartsResponse = {
  count: number;
  local_parts: UnknownEmailLocalPart[];
};

export type ApplyEmailCategoryRulesResponse = {
  updated_count: number;
  unknown_local_parts: UnknownEmailLocalPart[];
};
