import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import { Navigate, NavLink, Route, Routes, useSearchParams } from "react-router-dom";
import type { ChangeEvent, FormEvent, ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  Building2,
  CheckCircle2,
  ClipboardList,
  Copy,
  Download,
  ExternalLink,
  Globe2,
  Menu,
  Loader2,
  Mail,
  Megaphone,
  Phone,
  Play,
  RotateCw,
  Search,
  Settings,
  Star,
  Square,
  Table2,
  Trash2,
  X,
} from "lucide-react";
import { ApiError, type BusinessTypeEmailRule, type Campaign, type CampaignLead, type JobExecution, type JobStatus, type JobStepId, type Lead, type LeadEmail } from "./api";
import {
  useAddLeadEmail,
  useBackendHealth,
  useCampaign,
  useCampaignLeads,
  useCampaigns,
  useCreateCampaign,
  useDeleteLeadEmail,
  useBusinessTypeEmailRules,
  useApplyEmailCategoryRules,
  useEmailCategoryRules,
  useEmailSettings,
  useGenerateCampaignEmails,
  useGenerateCampaignLeadEmail,
  useGoogleMapsScrape,
  useJobPolling,
  useJobs,
  useLeadFilterOptions,
  useLeadEmails,
  useLeads,
  useLeadEmailEnrichment,
  useStopJob,
  useSummary,
  useUnknownEmailLocalParts,
  useUpdateBusinessTypeEmailRule,
  useUpdateCampaign,
  useUpdateCampaignLead,
  useUpdateEmailCategoryRule,
  useUpdateEmailSettings,
  useUpdateLeadEmail,
  useUpdateLead,
  useWebsiteEmailScrape,
} from "./hooks";
import { downloadCampaignExport, downloadExportedLeads } from "./hooks";

type PageId = "dashboard" | "discover" | "website" | "enrich" | "leads" | "campaigns" | "email-rules" | "jobs" | "settings";

const pages: Array<{ id: PageId; label: string; icon: typeof Activity }> = [
  { id: "dashboard", label: "Dashboard", icon: Activity },
  { id: "discover", label: "Find Businesses", icon: Building2 },
  { id: "website", label: "Website Emails", icon: Globe2 },
  { id: "enrich", label: "Enrich Leads", icon: Mail },
  { id: "leads", label: "Leads", icon: Table2 },
  { id: "campaigns", label: "Campaigns", icon: Megaphone },
  { id: "email-rules", label: "Email Rules", icon: Mail },
  { id: "jobs", label: "Jobs", icon: ClipboardList },
  { id: "settings", label: "Settings", icon: Settings },
];

const leadFlags = ["needs_review", "good", "bad", "hot"];
const leadStatuses = ["new", "reviewed", "ready", "contacted", "do_not_contact"];
const emailStatuses = ["new", "valid", "invalid", "do_not_use"];
const emailCategories = ["unknown", "booking", "info", "sales", "support", "accounting", "finance", "events", "hr", "marketing", "manager", "reception"];
const campaignStatuses = ["draft", "active", "paused", "completed", "archived"];

const pagePaths: Record<PageId, string> = {
  dashboard: "/dashboard",
  discover: "/discover",
  website: "/website-emails",
  enrich: "/enrich",
  leads: "/leads",
  campaigns: "/campaigns",
  "email-rules": "/email-rules",
  jobs: "/jobs",
  settings: "/settings",
};

function readStorageValue<T>(storage: Storage | undefined, key: string, fallback: T): T {
  if (!storage) return fallback;
  try {
    const raw = storage.getItem(key);
    return raw === null ? fallback : JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

function useBrowserStorageState<T>(
  storageType: "local" | "session",
  key: string,
  fallback: T,
) {
  const storage = typeof window === "undefined"
    ? undefined
    : storageType === "local"
      ? window.localStorage
      : window.sessionStorage;
  const [value, setValue] = useState<T>(() => readStorageValue(storage, key, fallback));

  useEffect(() => {
    if (!storage) return;
    try {
      storage.setItem(key, JSON.stringify(value));
    } catch {
      // Browser storage is best-effort UI persistence.
    }
  }, [key, storage, value]);

  return [value, setValue] as const;
}

function useLocalStorageState<T>(key: string, fallback: T) {
  return useBrowserStorageState("local", key, fallback);
}

function useSessionStorageState<T>(key: string, fallback: T) {
  return useBrowserStorageState("session", key, fallback);
}

function getSearchString(searchParams: URLSearchParams, key: string, fallback = "") {
  return searchParams.get(key) ?? fallback;
}

function getSearchNumber(searchParams: URLSearchParams, key: string, fallback: number) {
  const value = Number(searchParams.get(key));
  return Number.isFinite(value) && value > 0 ? value : fallback;
}

function getSearchBooleanString(searchParams: URLSearchParams, key: string, fallback = "") {
  const value = searchParams.get(key);
  return value === "true" || value === "false" ? value : fallback;
}

function getSearchPageSize(searchParams: URLSearchParams, key: string, fallback: number | "all") {
  const raw = searchParams.get(key);
  if (raw === "all") return "all";
  const value = Number(raw);
  return Number.isFinite(value) && value > 0 ? value : fallback;
}

function useUrlState() {
  const [searchParams, setSearchParams] = useSearchParams();

  const setParams = (
    values: Record<string, string | number | boolean | undefined | null>,
    options?: { replace?: boolean },
  ) => {
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      Object.entries(values).forEach(([key, value]) => {
        if (value === undefined || value === null || value === "") {
          next.delete(key);
        } else {
          next.set(key, String(value));
        }
      });
      return next;
    }, { replace: options?.replace ?? true });
  };

  const setParam = (key: string, value: string | number | boolean | undefined | null, options?: { replace?: boolean }) => {
    setParams({ [key]: value }, options);
  };

  return { searchParams, setParam, setParams };
}
const campaignStages = ["review", "ready_for_email", "drafted", "approved", "contacted", "replied", "closed", "skipped", "do_not_contact"];
const campaignPriorities = ["", "low", "normal", "high"];
const blockedEmailGenerationStages = new Set(["contacted", "replied", "closed", "skipped", "do_not_contact"]);

function normalizeCountOption(option: unknown) {
  if (typeof option === "string") {
    const value = option.trim();
    return value ? { value, count: 0 } : undefined;
  }

  if (typeof option === "object" && option !== null && "value" in option) {
    const value = String(option.value ?? "").trim();
    const count = Number("count" in option ? option.count : 0);
    return value ? { value, count: Number.isFinite(count) ? count : 0 } : undefined;
  }

  return undefined;
}

function optionLabel(option: { value: string; count: number }) {
  return option.count > 0 ? `${option.value} (${option.count})` : option.value;
}

function canGenerateEmailDraft(lead: CampaignLead) {
  return Boolean(
    (lead.primary_email || lead.emails) &&
    lead.lead_status !== "do_not_contact" &&
    !blockedEmailGenerationStages.has(lead.stage),
  );
}

function parseLeadLocation(value?: string | null) {
  if (!value) return {};
  if (!value.includes(":")) {
    const searchLocation = value.trim();
    return searchLocation ? { searchLocation } : {};
  }

  const [rawBusinessType, rawSearchLocation] = value.split(":", 2);
  const businessType = rawBusinessType.trim();
  const searchLocation = rawSearchLocation.trim();

  return {
    businessType: businessType || undefined,
    searchLocation: searchLocation || undefined,
  };
}

function errorMessage(error: unknown) {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Something went wrong.";
}

function StatusBadge({
  status,
}: {
  status?: string;
}) {
  const label = status ?? "unknown";
  return <span className={`status status-${label}`}>{label}</span>;
}

function FlagBadge({ flag }: { flag?: string | null }) {
  if (!flag) return <span className="muted">-</span>;
  return <span className={`flag flag-${flag}`}>{flag.replace("_", " ")}</span>;
}

function EditableFlagBadge({
  value,
  onChange,
  disabled = false,
}: {
  value?: string | null;
  onChange?: (value: string) => void;
  disabled?: boolean;
}) {
  if (!onChange) return <FlagBadge flag={value} />;
  const selectedValue = value || "needs_review";

  return (
    <select
      className={`badge-select flag flag-${selectedValue}`}
      value={selectedValue}
      disabled={disabled}
      title="Edit lead flag"
      onClick={(event) => event.stopPropagation()}
      onChange={(event) => onChange(event.target.value)}
    >
      {leadFlags.map((flag) => (
        <option value={flag} key={flag}>{flag.replace("_", " ")}</option>
      ))}
    </select>
  );
}

function EditableLeadStatusBadge({
  value,
  onChange,
  disabled = false,
}: {
  value?: string | null;
  onChange?: (value: string) => void;
  disabled?: boolean;
}) {
  if (!onChange) return value ? <StatusBadge status={value} /> : <span className="muted">-</span>;
  const selectedValue = value || "new";

  return (
    <select
      className={`badge-select status status-${selectedValue}`}
      value={selectedValue}
      disabled={disabled}
      title="Edit lead status"
      onClick={(event) => event.stopPropagation()}
      onChange={(event) => onChange(event.target.value)}
    >
      {leadStatuses.map((status) => (
        <option value={status} key={status}>{status.replace("_", " ")}</option>
      ))}
    </select>
  );
}

function PageHeader({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <header className="page-header">
      <h1>{title}</h1>
      <p>{description}</p>
    </header>
  );
}

function Field({
  label,
  children,
  className = "",
}: {
  label: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <label className={`field ${className}`.trim()}>
      <span>{label}</span>
      {children}
    </label>
  );
}

function AutoResizeTextarea({
  value,
  onChange,
  className = "",
}: {
  value: string;
  onChange: (event: ChangeEvent<HTMLTextAreaElement>) => void;
  className?: string;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const textarea = ref.current;
    if (!textarea) return;
    const maxHeight = 112;
    textarea.style.height = "auto";
    const nextHeight = Math.min(textarea.scrollHeight, maxHeight);
    textarea.style.height = `${nextHeight}px`;
    textarea.style.overflowY = textarea.scrollHeight > maxHeight ? "auto" : "hidden";
  }, [value]);

  return (
    <textarea
      ref={ref}
      className={className}
      value={value}
      onChange={onChange}
      rows={1}
    />
  );
}

function ErrorAlert({ error }: { error: unknown }) {
  if (!error) return null;
  return <div className="alert alert-error">{errorMessage(error)}</div>;
}

function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="empty-state">
      <strong>{title}</strong>
      <span>{body}</span>
    </div>
  );
}

function copyToClipboard(text: string) {
  if (!text) return;
  void navigator.clipboard.writeText(text);
}

function formatLeadAsText(lead: Lead) {
  return [
    lead.name,
    lead.address || lead.location,
    lead.phone ? `Phone: ${lead.phone}` : undefined,
    lead.website ? `Website: ${lead.website}` : undefined,
    lead.emails ? `Email: ${lead.emails}` : undefined,
  ].filter(Boolean).join("\n");
}

function EmailListCell({ emails }: { emails?: string | null }) {
  const items = (emails ?? "")
    .split(",")
    .map((email) => email.trim())
    .filter(Boolean);

  if (!items.length) return <>-</>;

  return (
    <>
      {items.map((email, index) => (
        <span className="email-token" key={`${email}-${index}`}>
          {email}
          {index < items.length - 1 ? "," : ""}
        </span>
      ))}
    </>
  );
}

function CampaignMembershipCell({ lead }: { lead: Lead }) {
  const count = lead.campaign_count ?? lead.campaign_names?.length ?? 0;
  const names = lead.campaign_names ?? [];

  if (!count) return <span className="muted">-</span>;

  return (
    <span className="campaign-badge" title={names.join(", ")}>
      {count === 1 ? names[0] : `${count} campaigns`}
    </span>
  );
}

type LeadHeaderFilters = {
  name: string;
  businessType: string;
  searchLocation: string;
  campaign: string;
  businessTypeOptions: Array<{ value: string; count: number }>;
  searchLocationOptions: Array<{ value: string; count: number }>;
  campaignOptions: Array<{ value: string; count: number }>;
  onNameChange: (value: string) => void;
  onBusinessTypeChange: (value: string) => void;
  onSearchLocationChange: (value: string) => void;
  onCampaignChange: (value: string) => void;
};

function LeadsTable({
  leads,
  selectedLeadId,
  headerFilters,
  onSelectLead,
  renderExpandedLead,
  onUpdateLeadFlag,
  onUpdateLeadStatus,
  updatingLeadId,
  showActions = false,
}: {
  leads: Lead[];
  selectedLeadId?: number;
  headerFilters?: LeadHeaderFilters;
  onSelectLead?: (lead: Lead) => void;
  renderExpandedLead?: (lead: Lead) => ReactNode;
  onUpdateLeadFlag?: (lead: Lead, value: string) => void;
  onUpdateLeadStatus?: (lead: Lead, value: string) => void;
  updatingLeadId?: number;
  showActions?: boolean;
}) {
  if (!leads.length && !headerFilters) {
    return (
      <EmptyState
        title="No leads to show"
        body="Run a business search or refresh exported leads after enrichment."
      />
    );
  }

  return (
    <div className="table-wrap">
      <table className={showActions ? "lead-table" : undefined}>
        <thead>
          <tr>
            <th>
              <div className="header-filter-cell header-filter-inline">
                <span>Name</span>
                {headerFilters && (
                  <input
                    className="header-search-input"
                    value={headerFilters.name}
                    onChange={(event) => headerFilters.onNameChange(event.target.value)}
                    placeholder="Search name"
                  />
                )}
              </div>
            </th>
            <th>
              <div className="header-filter-cell">
                {!headerFilters && <span>Location</span>}
                {headerFilters && (
                  <div className="header-filter-inline header-filter-location">
                    <select
                      className="header-filter-select compact"
                      value={headerFilters.businessType}
                      title={headerFilters.businessType || "Any business type"}
                      onChange={(event) => headerFilters.onBusinessTypeChange(event.target.value)}
                    >
                      <option value="">Type</option>
                      {headerFilters.businessTypeOptions.map((item) => (
                        <option value={item.value} key={item.value}>{optionLabel(item)}</option>
                      ))}
                    </select>
                    <select
                      className="header-filter-select compact"
                      value={headerFilters.searchLocation}
                      title={headerFilters.searchLocation || "Any location"}
                      onChange={(event) => headerFilters.onSearchLocationChange(event.target.value)}
                    >
                      <option value="">Location</option>
                      {headerFilters.searchLocationOptions.map((item) => (
                        <option value={item.value} key={item.value}>{optionLabel(item)}</option>
                      ))}
                    </select>
                  </div>
                )}
              </div>
            </th>
            <th>Phone</th>
            <th>Website</th>
            <th>Emails</th>
            <th>
              {headerFilters ? (
                <select
                  className="header-title-select"
                  value={headerFilters.campaign}
                  title={headerFilters.campaign || "Campaign"}
                  onChange={(event) => headerFilters.onCampaignChange(event.target.value)}
                >
                  <option value="">Campaign</option>
                  {headerFilters.campaignOptions.map((item) => (
                    <option value={item.value} key={item.value}>{optionLabel(item)}</option>
                  ))}
                </select>
              ) : (
                "Campaign"
              )}
            </th>
            <th>Flag</th>
            <th>Lead status</th>
            {showActions && <th>Actions</th>}
          </tr>
        </thead>
        <tbody>
          {!leads.length && (
            <tr>
              <td colSpan={showActions ? 9 : 8}>
                <EmptyState
                  title="No leads match these filters"
                  body="Adjust the table header filters or clear one of the sidebar filters."
                />
              </td>
            </tr>
          )}
          {leads.map((lead, index) => {
            const rowKey = `${lead.place_id ?? lead.lead_id ?? index}-${index}`;
            const isSelected = selectedLeadId === lead.lead_id;
            const columnCount = showActions ? 9 : 8;

            return (
              <Fragment key={rowKey}>
                <tr
                  className={[
                    isSelected ? "selected-row" : "",
                    onSelectLead ? "clickable-row" : "",
                    lead.status ? `lead-row-${lead.status}` : "",
                  ].filter(Boolean).join(" ")}
                  onClick={() => onSelectLead?.(lead)}
                >
                  <td>{lead.name || "Untitled"}</td>
                  <td>{lead.location || lead.address || "-"}</td>
                  <td className="phone-cell">{lead.phone || "-"}</td>
                  <td className="url-cell">
                    {lead.website ? (
                      <a href={lead.website} target="_blank" rel="noreferrer">
                        {lead.website}
                      </a>
                    ) : (
                      "-"
                    )}
                  </td>
                  <td className="email-cell"><EmailListCell emails={lead.emails} /></td>
                  <td><CampaignMembershipCell lead={lead} /></td>
                  <td>
                    <EditableFlagBadge
                      value={lead.lead_flag}
                      disabled={updatingLeadId === lead.lead_id}
                      onChange={onUpdateLeadFlag ? (value) => onUpdateLeadFlag(lead, value) : undefined}
                    />
                  </td>
                  <td>
                    <EditableLeadStatusBadge
                      value={lead.lead_status}
                      disabled={updatingLeadId === lead.lead_id}
                      onChange={onUpdateLeadStatus ? (value) => onUpdateLeadStatus(lead, value) : undefined}
                    />
                  </td>
                  {showActions && (
                    <td className="actions-cell">
                      <div className="actions-row">
                        <button
                          className="icon-button"
                          type="button"
                          disabled={!lead.website}
                          title={lead.website ? "Open website" : "No website"}
                          onClick={(event) => {
                            event.stopPropagation();
                            if (lead.website) window.open(lead.website, "_blank", "noopener,noreferrer");
                          }}
                        >
                          <ExternalLink size={15} />
                        </button>
                        <button
                          className="icon-button"
                          type="button"
                          disabled={!lead.emails}
                          title={lead.emails ? "Copy email" : "No email"}
                          onClick={(event) => {
                            event.stopPropagation();
                            copyToClipboard(lead.emails ?? "");
                          }}
                        >
                          <Mail size={15} />
                        </button>
                        <button
                          className="icon-button"
                          type="button"
                          disabled={!lead.phone}
                          title={lead.phone ? "Copy phone" : "No phone"}
                          onClick={(event) => {
                            event.stopPropagation();
                            copyToClipboard(lead.phone ?? "");
                          }}
                        >
                          <Phone size={15} />
                        </button>
                        <button
                          className="icon-button"
                          type="button"
                          title="Copy lead"
                          onClick={(event) => {
                            event.stopPropagation();
                            copyToClipboard(formatLeadAsText(lead));
                          }}
                        >
                          <Copy size={15} />
                        </button>
                      </div>
                    </td>
                  )}
                </tr>
                {isSelected && renderExpandedLead && (
                  <tr className="expanded-detail-row">
                    <td colSpan={columnCount}>
                      {renderExpandedLead(lead)}
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function JobsTable({
  jobs,
  selectedJobId,
  onSelectJob,
  onStopJob,
  stoppingJobId,
  renderExpandedJob,
}: {
  jobs: JobExecution[];
  selectedJobId?: string;
  onSelectJob?: (job: JobExecution) => void;
  onStopJob?: (jobId: string) => void;
  stoppingJobId?: string;
  renderExpandedJob?: (job: JobExecution) => ReactNode;
}) {
  if (!jobs.length) {
    return <EmptyState title="No jobs found" body="Run a scrape or enrichment workflow to create job history." />;
  }

  const showActions = Boolean(onSelectJob || onStopJob);

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Job ID</th>
            <th>Step</th>
            <th>Input</th>
            <th>Status</th>
            <th>Progress</th>
            <th>Updated</th>
            {showActions && <th>Actions</th>}
          </tr>
        </thead>
        <tbody>
          {jobs.map((job) => {
            const isSelected = selectedJobId === job.job_id;
            const columnCount = showActions ? 7 : 6;

            return (
              <Fragment key={`${job.execution_id}-${job.job_id}`}>
                <tr
                  className={[
                    isSelected ? "selected-row" : "",
                    onSelectJob ? "clickable-row" : "",
                  ].filter(Boolean).join(" ")}
                  onClick={() => onSelectJob?.(job)}
                >
                  <td className="mono">{job.job_id}</td>
                  <td>{job.step_id}</td>
                  <td>{job.input}</td>
                  <td><StatusBadge status={job.status} /></td>
                  <td>{job.current_row ?? 0} / {job.total_rows ?? 0}</td>
                  <td>{job.updated_at}</td>
                  {showActions && (
                    <td className="actions-cell">
                      {onSelectJob && (
                        <button
                          className="text-button"
                          type="button"
                          onClick={(event) => {
                            event.stopPropagation();
                            onSelectJob(job);
                          }}
                        >
                          Details
                        </button>
                      )}
                      {onStopJob && job.status === "running" && (
                        <button
                          className="text-button danger-text"
                          type="button"
                          disabled={stoppingJobId === job.job_id}
                          onClick={(event) => {
                            event.stopPropagation();
                            onStopJob(job.job_id);
                          }}
                        >
                          {stoppingJobId === job.job_id ? "Stopping" : "Stop"}
                        </button>
                      )}
                    </td>
                  )}
                </tr>
                {isSelected && renderExpandedJob && (
                  <tr className="expanded-detail-row">
                    <td colSpan={columnCount}>
                      {renderExpandedJob(job)}
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function MetricCard({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: number;
  tone?: "neutral" | "good" | "warning" | "bad";
}) {
  return (
    <div className={`metric-card metric-${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function DashboardPage() {
  const health = useBackendHealth();
  const summary = useSummary();
  const jobs = useJobs({ limit: 8 });

  return (
    <>
      <PageHeader
        title="Dashboard"
        description="Monitor backend connectivity and start the scraping workflows from the sidebar."
      />
      <section className="grid two">
        <div className="panel">
          <div className="panel-title">
            <Activity size={18} />
            Backend
          </div>
          {health.isLoading ? (
            <div className="muted">Checking backend...</div>
          ) : health.isError ? (
            <div className="alert alert-error">{errorMessage(health.error)}</div>
          ) : (
            <div className="stack">
              <StatusBadge status={health.data?.status} />
              <span className="muted">{health.data?.message}</span>
            </div>
          )}
        </div>
        <div className="panel">
          <div className="panel-title">
            <CheckCircle2 size={18} />
            Workflow
          </div>
          <ol className="workflow-list">
            <li>Find businesses from Google Places.</li>
            <li>Enrich stored leads with website email scraping.</li>
            <li>Review and export contact-ready leads.</li>
          </ol>
        </div>
      </section>
      <section className="panel">
        <div className="section-head">
          <div>
            <h2>Pipeline summary</h2>
            <p>Lead and job counts from the local database</p>
          </div>
        </div>
        {summary.isLoading ? (
          <div className="muted">Loading summary...</div>
        ) : summary.isError ? (
          <ErrorAlert error={summary.error} />
        ) : summary.data ? (
          <div className="metrics-grid">
            <MetricCard label="Total leads" value={summary.data.leads.total} />
            <MetricCard label="With websites" value={summary.data.leads.with_website} />
            <MetricCard label="With emails" value={summary.data.leads.with_email} tone="good" />
            <MetricCard label="Pending enrichment" value={summary.data.leads.pending_enrichment} tone="warning" />
            <MetricCard label="Failed leads" value={summary.data.leads.failed} tone="bad" />
            <MetricCard label="Running jobs" value={summary.data.jobs.running} tone="warning" />
          </div>
        ) : null}
      </section>
      <section className="panel">
        <div className="section-head">
          <div>
            <h2>Recent jobs</h2>
            <p>{jobs.data?.count ?? 0} latest executions</p>
          </div>
        </div>
        {jobs.isLoading ? (
          <div className="muted">Loading jobs...</div>
        ) : jobs.isError ? (
          <ErrorAlert error={jobs.error} />
        ) : (
          <JobsTable jobs={jobs.data?.jobs ?? []} />
        )}
      </section>
    </>
  );
}

function DiscoverPage() {
  const scrape = useGoogleMapsScrape();
  const { searchParams, setParam } = useUrlState();
  const location = getSearchString(searchParams, "location");
  const placeType = getSearchString(searchParams, "place_type", "lodging");
  const maxPlaces = getSearchNumber(searchParams, "max_places", 20);
  const setLocation = (value: string) => setParam("location", value);
  const setPlaceType = (value: string) => setParam("place_type", value);
  const setMaxPlaces = (value: number) => setParam("max_places", value);

  function submit(event: FormEvent) {
    event.preventDefault();
    scrape.mutate({
      location,
      place_type: placeType,
      max_places: maxPlaces,
    });
  }

  return (
    <>
      <PageHeader
        title="Find Businesses"
        description="Search Google Places by location and business type, then store the returned leads."
      />
      <form className="panel form-panel" onSubmit={submit}>
        <Field label="Location">
          <input
            required
            value={location}
            onChange={(event) => setLocation(event.target.value)}
            placeholder="Sarande, Albania"
          />
        </Field>
        <Field label="Business type">
          <input
            required
            value={placeType}
            onChange={(event) => setPlaceType(event.target.value)}
            placeholder="lodging"
          />
        </Field>
        <Field label="Max places">
          <input
            min={1}
            max={100}
            type="number"
            value={maxPlaces}
            onChange={(event) => setMaxPlaces(Number(event.target.value))}
          />
        </Field>
        <button type="submit" disabled={scrape.isPending}>
          {scrape.isPending ? <Loader2 className="spin" size={17} /> : <Search size={17} />}
          Search
        </button>
      </form>
      <ErrorAlert error={scrape.error} />
      {scrape.data && (
        <section className="panel">
          <div className="section-head">
            <div>
              <h2>Results</h2>
              <p>{scrape.data.leads.length} leads stored for {scrape.data.input}</p>
            </div>
            <StatusBadge status={scrape.data.status} />
          </div>
          <LeadsTable leads={scrape.data.leads} />
        </section>
      )}
    </>
  );
}

function WebsiteEmailPage() {
  const scrape = useWebsiteEmailScrape();
  const { searchParams, setParam } = useUrlState();
  const url = getSearchString(searchParams, "url");
  const maxPages = getSearchNumber(searchParams, "max_pages", 10);
  const sitemapLimit = getSearchNumber(searchParams, "sitemap_limit", 10);
  const headless = getSearchBooleanString(searchParams, "headless", "true") !== "false";
  const useTor = getSearchBooleanString(searchParams, "use_tor", "false") === "true";
  const setUrl = (value: string) => setParam("url", value);
  const setMaxPages = (value: number) => setParam("max_pages", value);
  const setSitemapLimit = (value: number) => setParam("sitemap_limit", value);
  const setHeadless = (value: boolean) => setParam("headless", value);
  const setUseTor = (value: boolean) => setParam("use_tor", value);

  function submit(event: FormEvent) {
    event.preventDefault();
    scrape.mutate({
      url,
      max_pages: maxPages,
      sitemap_limit: sitemapLimit,
      headless,
      use_tor: useTor,
    });
  }

  return (
    <>
      <PageHeader
        title="Website Emails"
        description="Run a one-off Selenium scrape against a single website and return email addresses."
      />
      <form className="panel form-panel" onSubmit={submit}>
        <Field label="Website URL">
          <input
            required
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            placeholder="https://example.com"
          />
        </Field>
        <div className="form-row">
          <Field label="Max pages">
            <input
              min={1}
              max={100}
              type="number"
              value={maxPages}
              onChange={(event) => setMaxPages(Number(event.target.value))}
            />
          </Field>
          <Field label="Sitemap limit">
            <input
              min={1}
              max={50}
              type="number"
              value={sitemapLimit}
              onChange={(event) => setSitemapLimit(Number(event.target.value))}
            />
          </Field>
        </div>
        <div className="toggle-row">
          <label>
            <input
              type="checkbox"
              checked={headless}
              onChange={(event) => setHeadless(event.target.checked)}
            />
            Headless browser
          </label>
          <label>
            <input
              type="checkbox"
              checked={useTor}
              onChange={(event) => setUseTor(event.target.checked)}
            />
            Use Tor
          </label>
        </div>
        <button type="submit" disabled={scrape.isPending}>
          {scrape.isPending ? <Loader2 className="spin" size={17} /> : <Play size={17} />}
          Start scrape
        </button>
      </form>
      <ErrorAlert error={scrape.error} />
      {scrape.data && (
        <section className="panel">
          <div className="section-head">
            <div>
              <h2>Emails</h2>
              <p>{scrape.data.emails.length} found on {scrape.data.input}</p>
            </div>
            <StatusBadge status={scrape.data.status} />
          </div>
          {scrape.data.emails.length ? (
            <div className="chips">
              {scrape.data.emails.map((email) => (
                <span className="chip" key={email}>{email}</span>
              ))}
            </div>
          ) : (
            <EmptyState title="No emails found" body="Try increasing max pages or checking the website manually." />
          )}
        </section>
      )}
    </>
  );
}

function JobProgressPanel({ jobId }: { jobId?: string }) {
  const progress = useJobPolling(jobId);
  const stop = useStopJob();
  const percent = useMemo(() => {
    const current = progress.data?.current_row ?? 0;
    const total = progress.data?.total_rows ?? 0;
    return total > 0 ? Math.min(100, Math.round((current / total) * 100)) : 0;
  }, [progress.data]);

  if (!jobId) return null;

  return (
    <section className="panel">
      <div className="section-head">
        <div>
          <h2>Job progress</h2>
          <p className="mono">{jobId}</p>
        </div>
        {progress.data && <StatusBadge status={progress.data.status} />}
      </div>
      {progress.isLoading ? (
        <div className="muted">Loading progress...</div>
      ) : progress.isError ? (
        <ErrorAlert error={progress.error} />
      ) : (
        <div className="stack">
          <div className="progress">
            <span style={{ width: `${percent}%` }} />
          </div>
          <div className="progress-meta">
            <span>{progress.data?.current_row ?? 0} / {progress.data?.total_rows ?? 0}</span>
            <span>{percent}%</span>
          </div>
          {progress.data?.error_message && (
            <div className="alert alert-error">{progress.data.error_message}</div>
          )}
          {progress.data?.status === "running" && (
            <button
              className="secondary danger"
              type="button"
              disabled={stop.isPending}
              onClick={() => stop.mutate(jobId)}
            >
              {stop.isPending ? <Loader2 className="spin" size={17} /> : <Square size={17} />}
              Stop job
            </button>
          )}
        </div>
      )}
    </section>
  );
}

function JobDetailPanel({ jobId }: { jobId?: string }) {
  const progress = useJobPolling(jobId);
  const percent = useMemo(() => {
    const current = progress.data?.current_row ?? 0;
    const total = progress.data?.total_rows ?? 0;
    return total > 0 ? Math.min(100, Math.round((current / total) * 100)) : 0;
  }, [progress.data]);

  if (!jobId) return null;

  return (
    <section className="panel">
      <div className="section-head">
        <div>
          <h2>Job details</h2>
          <p className="mono">{jobId}</p>
        </div>
        {progress.data && <StatusBadge status={progress.data.status} />}
      </div>
      {progress.isLoading ? (
        <div className="muted">Loading job details...</div>
      ) : progress.isError ? (
        <ErrorAlert error={progress.error} />
      ) : progress.data ? (
        <div className="detail-grid">
          <div>
            <span className="label">Step</span>
            <strong>{progress.data.step_id}</strong>
          </div>
          <div>
            <span className="label">Input</span>
            <strong>{progress.data.input}</strong>
          </div>
          <div>
            <span className="label">Max pages</span>
            <strong>{progress.data.max_pages ?? "-"}</strong>
          </div>
          <div>
            <span className="label">Browser</span>
            <strong>{progress.data.headless ? "Headless" : "Visible"}</strong>
          </div>
          <div className="detail-wide">
            <span className="label">Progress</span>
            <div className="progress">
              <span style={{ width: `${percent}%` }} />
            </div>
            <div className="progress-meta">
              <span>{progress.data.current_row ?? 0} / {progress.data.total_rows ?? 0}</span>
              <span>{percent}%</span>
            </div>
          </div>
          {progress.data.error_message && (
            <div className="detail-wide alert alert-error">{progress.data.error_message}</div>
          )}
        </div>
      ) : null}
    </section>
  );
}

function JobsPage() {
  const { searchParams, setParam } = useUrlState();
  const status = getSearchString(searchParams, "status");
  const stepId = getSearchString(searchParams, "step_id");
  const limit = getSearchNumber(searchParams, "limit", 50);
  const selectedJobId = getSearchString(searchParams, "job_id") || undefined;
  const setStatus = (value: string) => setParam("status", value);
  const setStepId = (value: string) => setParam("step_id", value);
  const setLimit = (value: number) => setParam("limit", value);
  const setSelectedJobId = (value?: string) => setParam("job_id", value ?? "", { replace: false });
  const jobs = useJobs({
    status: status === "" ? undefined : status as JobStatus,
    step_id: stepId === "" ? undefined : stepId as JobStepId,
    limit,
  });
  const stop = useStopJob();

  return (
    <>
      <PageHeader
        title="Jobs"
        description="Browse job history, filter executions, inspect progress, and stop running jobs."
      />
      <section className="panel job-filters">
        <Field label="Status">
          <select value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="">Any status</option>
            <option value="running">Running</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
            <option value="stopped">Stopped</option>
          </select>
        </Field>
        <Field label="Step">
          <select value={stepId} onChange={(event) => setStepId(event.target.value)}>
            <option value="">Any step</option>
            <option value="email_scrape">Website email scrape</option>
            <option value="google_maps_scrape">Google Maps scrape</option>
            <option value="leads_email_scrape">Lead email enrichment</option>
          </select>
        </Field>
        <Field label="Limit">
          <input
            type="number"
            min={1}
            max={200}
            value={limit}
            onChange={(event) => setLimit(Number(event.target.value))}
          />
        </Field>
      </section>
      <section className="jobs-layout">
        <section className="panel">
          <div className="section-head">
            <div>
              <h2>Job history</h2>
              <p>{jobs.data?.count ?? 0} matching executions</p>
            </div>
          </div>
          {jobs.isLoading ? (
            <div className="muted">Loading jobs...</div>
          ) : jobs.isError ? (
            <ErrorAlert error={jobs.error} />
          ) : (
            <JobsTable
              jobs={jobs.data?.jobs ?? []}
              selectedJobId={selectedJobId}
              onSelectJob={(job) => setSelectedJobId(selectedJobId === job.job_id ? undefined : job.job_id)}
              onStopJob={(jobId) => stop.mutate(jobId)}
              stoppingJobId={stop.isPending ? stop.variables : undefined}
              renderExpandedJob={(job) => <JobDetailPanel jobId={job.job_id} />}
            />
          )}
        </section>
      </section>
    </>
  );
}

function EnrichPage() {
  const enrich = useLeadEmailEnrichment();
  const { searchParams, setParam } = useUrlState();
  const jobId = getSearchString(searchParams, "job_id") || undefined;
  const maxPages = getSearchNumber(searchParams, "max_pages", 30);
  const headless = getSearchBooleanString(searchParams, "headless", "true") !== "false";
  const useTor = getSearchBooleanString(searchParams, "use_tor", "false") === "true";
  const setJobId = (value?: string) => setParam("job_id", value ?? "", { replace: false });
  const setMaxPages = (value: number) => setParam("max_pages", value);
  const setHeadless = (value: boolean) => setParam("headless", value);
  const setUseTor = (value: boolean) => setParam("use_tor", value);

  function submit(event: FormEvent) {
    event.preventDefault();
    enrich.mutate(
      { max_pages: maxPages, headless, use_tor: useTor },
      {
        onSuccess: (response) => {
          if ("job_id" in response) setJobId(response.job_id);
        },
      },
    );
  }

  return (
    <>
      <PageHeader
        title="Enrich Leads"
        description="Scrape emails for stored leads that have websites and are not already marked scraped."
      />
      <form className="panel form-panel" onSubmit={submit}>
        <Field label="Max pages per lead">
          <input
            min={1}
            max={100}
            type="number"
            value={maxPages}
            onChange={(event) => setMaxPages(Number(event.target.value))}
          />
        </Field>
        <div className="toggle-row">
          <label>
            <input
              type="checkbox"
              checked={headless}
              onChange={(event) => setHeadless(event.target.checked)}
            />
            Headless browser
          </label>
          <label>
            <input
              type="checkbox"
              checked={useTor}
              onChange={(event) => setUseTor(event.target.checked)}
            />
            Use Tor
          </label>
        </div>
        <button type="submit" disabled={enrich.isPending}>
          {enrich.isPending ? <Loader2 className="spin" size={17} /> : <Play size={17} />}
          Start enrichment
        </button>
      </form>
      <ErrorAlert error={enrich.error} />
      {enrich.data && "message" in enrich.data && (
        <div className="alert">{enrich.data.message}</div>
      )}
      <JobProgressPanel jobId={jobId} />
    </>
  );
}

function EmailReviewRow({
  email,
  onUpdate,
  onDelete,
}: {
  email: LeadEmail;
  onUpdate: (payload: {
    category?: string;
    status?: string;
    is_primary?: boolean;
    notes?: string;
  }) => void;
  onDelete: () => void;
}) {
  return (
    <div className="email-review-row">
      <div className="email-review-main">
        <strong>{email.email}</strong>
        <div className="email-review-meta">
          {email.is_primary ? <span className="flag flag-hot">primary</span> : null}
          <StatusBadge status={email.status} />
          <span className="muted">{email.category}</span>
        </div>
      </div>
      <select
        value={email.category}
        onChange={(event) => onUpdate({ category: event.target.value })}
      >
        {emailCategories.map((category) => (
          <option value={category} key={category}>{category}</option>
        ))}
      </select>
      <select
        value={email.status}
        onChange={(event) => onUpdate({ status: event.target.value })}
      >
        {emailStatuses.map((status) => (
          <option value={status} key={status}>{status.replace("_", " ")}</option>
        ))}
      </select>
      <div className="email-review-actions">
        <button
          className="icon-button"
          type="button"
          title="Mark primary"
          disabled={Boolean(email.is_primary)}
          onClick={() => onUpdate({ is_primary: true })}
        >
          <Star size={15} />
        </button>
        <button
          className="icon-button"
          type="button"
          title="Copy email"
          onClick={() => copyToClipboard(email.email)}
        >
          <Copy size={15} />
        </button>
        <button
          className="icon-button danger-text"
          type="button"
          title="Delete email"
          onClick={onDelete}
        >
          <Trash2 size={15} />
        </button>
      </div>
    </div>
  );
}

function LeadDetailPanel({
  lead,
  onLeadUpdated,
}: {
  lead?: Lead;
  onLeadUpdated?: (lead: Lead) => void;
}) {
  const updateLead = useUpdateLead();
  const leadEmails = useLeadEmails(lead?.lead_id);
  const addEmail = useAddLeadEmail();
  const updateEmail = useUpdateLeadEmail();
  const deleteEmail = useDeleteLeadEmail();
  const [website, setWebsite] = useState("");
  const [emails, setEmails] = useState("");
  const [status, setStatus] = useState("");
  const [notes, setNotes] = useState("");
  const [websiteSummary, setWebsiteSummary] = useState("");
  const [newEmail, setNewEmail] = useState("");

  useEffect(() => {
    setWebsite(lead?.website ?? "");
    setEmails(lead?.emails ?? "");
    setStatus(lead?.status ?? "");
    setNotes(lead?.notes ?? "");
    setWebsiteSummary(lead?.website_summary ?? "");
  }, [lead]);

  if (!lead) return null;

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!lead?.lead_id) return;
    updateLead.mutate({
      leadId: lead.lead_id,
      payload: {
        website,
        emails,
        status,
        notes,
        website_summary: websiteSummary,
      },
    }, {
      onSuccess: (response) => onLeadUpdated?.(response.lead),
    });
  }

  return (
    <section className="panel">
      <div className="section-head">
        <div>
          <h2>{lead.name || "Untitled lead"}</h2>
          <p>
            {lead.address || lead.location || "No location"}
            <span className="header-meta mono">{lead.job_id || "-"}</span>
          </p>
        </div>
        <div className="stack">
          <EditableFlagBadge
            value={lead.lead_flag}
            disabled={updateLead.isPending}
            onChange={(value) => {
              if (!lead.lead_id) return;
              updateLead.mutate(
                { leadId: lead.lead_id, payload: { lead_flag: value } },
                { onSuccess: (response) => onLeadUpdated?.(response.lead) },
              );
            }}
          />
          <EditableLeadStatusBadge
            value={lead.lead_status}
            disabled={updateLead.isPending}
            onChange={(value) => {
              if (!lead.lead_id) return;
              updateLead.mutate(
                { leadId: lead.lead_id, payload: { lead_status: value } },
                { onSuccess: (response) => onLeadUpdated?.(response.lead) },
              );
            }}
          />
        </div>
      </div>
      <div className="detail-grid">
        <div>
          <span className="label">Phone</span>
          <strong>{lead.phone || "-"}</strong>
        </div>
        <div>
          <span className="label">Created</span>
          <strong>{lead.created_at || "-"}</strong>
        </div>
        <div>
          <span className="label">Updated</span>
          <strong>{lead.updated_at || "-"}</strong>
        </div>
        <div>
          <span className="label">Summary status</span>
          <strong>{lead.summary_status || "-"}</strong>
        </div>
        <div className="detail-wide">
          <span className="label">Campaigns</span>
          {lead.campaign_memberships?.length ? (
            <div className="chips">
              {lead.campaign_memberships.map((membership) => (
                <span className="chip" key={`${membership.campaign_id}-${membership.stage}`}>
                  {membership.campaign_name} - {membership.stage.replace("_", " ")}
                </span>
              ))}
            </div>
          ) : (
            <strong>-</strong>
          )}
        </div>
      </div>
      <form className="edit-form" onSubmit={submit}>
        <Field label="Website">
          <input value={website} onChange={(event) => setWebsite(event.target.value)} />
        </Field>
        <Field label="Emails">
          <input value={emails} onChange={(event) => setEmails(event.target.value)} />
        </Field>
        <Field label="Status">
          <select value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="">No status</option>
            <option value="scraped">Scraped</option>
            <option value="failed">Failed</option>
            <option value="skipped">Skipped</option>
            <option value="pending">Pending</option>
          </select>
        </Field>
        <div className="large-text-row">
          <Field label="Notes" className="large-text-field">
            <AutoResizeTextarea value={notes} onChange={(event) => setNotes(event.target.value)} />
          </Field>
          <Field label="Website context" className="large-text-field">
            <AutoResizeTextarea
              className="summary-textarea"
              value={websiteSummary}
              onChange={(event) => setWebsiteSummary(event.target.value)}
            />
          </Field>
        </div>
        <button type="submit" disabled={updateLead.isPending || !lead.lead_id}>
          {updateLead.isPending ? <Loader2 className="spin" size={17} /> : <CheckCircle2 size={17} />}
          Save lead
        </button>
        <ErrorAlert error={updateLead.error} />
      </form>
      <section className="email-review">
        <div className="section-head">
          <div>
            <h2>Email review</h2>
            <p>{leadEmails.data?.count ?? 0} emails on this lead</p>
          </div>
        </div>
        {leadEmails.isLoading ? (
          <div className="muted">Loading emails...</div>
        ) : leadEmails.isError ? (
          <ErrorAlert error={leadEmails.error} />
        ) : (
          <div className="email-review-list">
            {(leadEmails.data?.emails ?? []).map((email) => (
              <EmailReviewRow
                key={email.email_id}
                email={email}
                onUpdate={(payload) => updateEmail.mutate({
                  emailId: email.email_id,
                  leadId: email.lead_id,
                  payload,
                })}
                onDelete={() => deleteEmail.mutate({
                  emailId: email.email_id,
                  leadId: email.lead_id,
                })}
              />
            ))}
            {!leadEmails.data?.emails.length && (
              <EmptyState title="No reviewed emails" body="Add an email manually or run enrichment for this lead." />
            )}
          </div>
        )}
        <form
          className="add-email-form"
          onSubmit={(event) => {
            event.preventDefault();
            if (!lead.lead_id || !newEmail.trim()) return;
            addEmail.mutate({
              leadId: lead.lead_id,
              payload: {
                email: newEmail.trim(),
                category: "unknown",
                status: "new",
              },
            }, {
              onSuccess: () => setNewEmail(""),
            });
          }}
        >
          <input
            value={newEmail}
            onChange={(event) => setNewEmail(event.target.value)}
            placeholder="Add email"
          />
          <button type="submit" disabled={addEmail.isPending || !newEmail.trim()}>
            Add
          </button>
        </form>
        <ErrorAlert error={addEmail.error || updateEmail.error || deleteEmail.error} />
      </section>
    </section>
  );
}

function LeadsPage() {
  const { searchParams, setParam } = useUrlState();
  const [preferredPageSize, setPreferredPageSize] = useLocalStorageState<number | "all">("scraping-console:leads-page-size", 30);
  const status = getSearchString(searchParams, "status");
  const jobId = getSearchString(searchParams, "job_id");
  const hasEmail = getSearchBooleanString(searchParams, "has_email");
  const hasWebsite = getSearchBooleanString(searchParams, "has_website");
  const hasPhone = getSearchBooleanString(searchParams, "has_phone");
  const nameColumnFilter = getSearchString(searchParams, "name");
  const businessTypeColumnFilter = getSearchString(searchParams, "business_type");
  const searchLocationColumnFilter = getSearchString(searchParams, "search_location");
  const campaignColumnFilter = getSearchString(searchParams, "campaign");
  const leadFlagFilter = getSearchString(searchParams, "lead_flag");
  const leadStatusFilter = getSearchString(searchParams, "lead_status");
  const selectedLeadId = getSearchNumber(searchParams, "lead_id", 0);
  const pageSize = getSearchPageSize(searchParams, "page_size", preferredPageSize);
  const page = getSearchNumber(searchParams, "page", 1);
  const setStatus = (value: string) => setParam("status", value);
  const setJobId = (value: string) => setParam("job_id", value);
  const setHasEmail = (value: string) => setParam("has_email", value);
  const setHasWebsite = (value: string) => setParam("has_website", value);
  const setHasPhone = (value: string) => setParam("has_phone", value);
  const setNameColumnFilter = (value: string) => setParam("name", value);
  const setBusinessTypeColumnFilter = (value: string) => setParam("business_type", value);
  const setSearchLocationColumnFilter = (value: string) => setParam("search_location", value);
  const setCampaignColumnFilter = (value: string) => setParam("campaign", value);
  const setLeadFlagFilter = (value: string) => setParam("lead_flag", value);
  const setLeadStatusFilter = (value: string) => setParam("lead_status", value);
  const setSelectedLead = (lead?: Lead) => setParam("lead_id", lead?.lead_id ?? "", { replace: false });
  const setPageSize = (value: number | "all") => {
    setPreferredPageSize(value);
    setParam("page_size", value);
  };
  const setPage = (value: React.SetStateAction<number>) => {
    const nextPage = typeof value === "function" ? value(page) : value;
    setParam("page", Math.max(1, nextPage), { replace: false });
  };
  const updateLeadReview = useUpdateLead();
  const leads = useLeads({
    status: status || undefined,
    job_id: jobId || undefined,
    has_email: hasEmail === "" ? undefined : hasEmail === "true",
    has_website: hasWebsite === "" ? undefined : hasWebsite === "true",
    has_phone: hasPhone === "" ? undefined : hasPhone === "true",
    lead_flag: leadFlagFilter || undefined,
    lead_status: leadStatusFilter || undefined,
  });
  const serverLeads = leads.data?.leads ?? [];
  const selectedLead = serverLeads.find((lead) => lead.lead_id === selectedLeadId);
  const businessTypeOptions = useMemo(() => {
    const counts = new Map<string, number>();
    serverLeads.forEach((lead) => {
      const parsed = parseLeadLocation(lead.location);
      if (!parsed.businessType) return;
      if (searchLocationColumnFilter && parsed.searchLocation !== searchLocationColumnFilter) return;
      counts.set(parsed.businessType, (counts.get(parsed.businessType) ?? 0) + 1);
    });
    return [...counts.entries()]
      .map(([value, count]) => ({ value, count }))
      .sort((a, b) => a.value.localeCompare(b.value));
  }, [searchLocationColumnFilter, serverLeads]);
  const searchLocationOptions = useMemo(() => {
    const counts = new Map<string, number>();
    serverLeads.forEach((lead) => {
      const parsed = parseLeadLocation(lead.location);
      if (!parsed.searchLocation) return;
      if (businessTypeColumnFilter && parsed.businessType !== businessTypeColumnFilter) return;
      counts.set(parsed.searchLocation, (counts.get(parsed.searchLocation) ?? 0) + 1);
    });
    return [...counts.entries()]
      .map(([value, count]) => ({ value, count }))
      .sort((a, b) => a.value.localeCompare(b.value));
  }, [businessTypeColumnFilter, serverLeads]);
  const campaignOptions = useMemo(() => {
    const counts = new Map<string, number>();
    serverLeads.forEach((lead) => {
      (lead.campaign_names ?? []).forEach((campaignName) => {
        counts.set(campaignName, (counts.get(campaignName) ?? 0) + 1);
      });
    });
    return [...counts.entries()]
      .map(([value, count]) => ({ value, count }))
      .sort((a, b) => a.value.localeCompare(b.value));
  }, [serverLeads]);
  const allLeads = useMemo(() => {
    const normalizedName = nameColumnFilter.trim().toLowerCase();
    return serverLeads.filter((lead) => {
      const parsed = parseLeadLocation(lead.location);
      if (normalizedName && !(lead.name ?? "").toLowerCase().includes(normalizedName)) return false;
      if (businessTypeColumnFilter && parsed.businessType !== businessTypeColumnFilter) return false;
      if (searchLocationColumnFilter && parsed.searchLocation !== searchLocationColumnFilter) return false;
      if (campaignColumnFilter && !(lead.campaign_names ?? []).includes(campaignColumnFilter)) return false;
      return true;
    });
  }, [businessTypeColumnFilter, campaignColumnFilter, nameColumnFilter, searchLocationColumnFilter, serverLeads]);

  useEffect(() => {
    if (!businessTypeColumnFilter) return;
    const isValid = businessTypeOptions.some((item) => item.value === businessTypeColumnFilter);
    if (!isValid) setBusinessTypeColumnFilter("");
  }, [businessTypeColumnFilter, businessTypeOptions]);

  useEffect(() => {
    if (!searchLocationColumnFilter) return;
    const isValid = searchLocationOptions.some((item) => item.value === searchLocationColumnFilter);
    if (!isValid) setSearchLocationColumnFilter("");
  }, [searchLocationColumnFilter, searchLocationOptions]);
  const totalPages = pageSize === "all" ? 1 : Math.max(1, Math.ceil(allLeads.length / pageSize));
  const currentPage = Math.min(page, totalPages);
  const visibleLeads = pageSize === "all"
    ? allLeads
    : allLeads.slice((currentPage - 1) * pageSize, currentPage * pageSize);
  const didMountLeadFilters = useRef(false);

  useEffect(() => {
    if (!didMountLeadFilters.current) {
      didMountLeadFilters.current = true;
      return;
    }
    setPage(1);
  }, [nameColumnFilter, status, jobId, hasEmail, hasWebsite, hasPhone, businessTypeColumnFilter, searchLocationColumnFilter, campaignColumnFilter, leadFlagFilter, leadStatusFilter, pageSize]);

  useEffect(() => {
    if (selectedLeadId && leads.isSuccess && !selectedLead) setSelectedLead(undefined);
  }, [leads.isSuccess, selectedLead, selectedLeadId]);

  return (
    <>
      <PageHeader
        title="Leads"
        description="Review all stored leads, filter by status or job, and export contact-ready records."
      />
      <section className="panel filters">
        <Field label="Status">
          <select value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="">Any status</option>
            <option value="scraped">Scraped</option>
            <option value="failed">Failed</option>
            <option value="skipped">Skipped</option>
            <option value="pending">Pending</option>
          </select>
        </Field>
        <Field label="Job ID">
          <input
            value={jobId}
            onChange={(event) => setJobId(event.target.value)}
            placeholder="Filter by job UUID"
          />
        </Field>
        <Field label="Email">
          <select value={hasEmail} onChange={(event) => setHasEmail(event.target.value)}>
            <option value="">Any</option>
            <option value="true">Has email</option>
            <option value="false">No email</option>
          </select>
        </Field>
        <Field label="Website">
          <select value={hasWebsite} onChange={(event) => setHasWebsite(event.target.value)}>
            <option value="">Any</option>
            <option value="true">Has website</option>
            <option value="false">No website</option>
          </select>
        </Field>
        <Field label="Phone">
          <select value={hasPhone} onChange={(event) => setHasPhone(event.target.value)}>
            <option value="">Any</option>
            <option value="true">Has phone</option>
            <option value="false">No phone</option>
          </select>
        </Field>
        <Field label="Flag">
          <select value={leadFlagFilter} onChange={(event) => setLeadFlagFilter(event.target.value)}>
            <option value="">Any flag</option>
            {leadFlags.map((flag) => (
              <option value={flag} key={flag}>{flag.replace("_", " ")}</option>
            ))}
          </select>
        </Field>
        <Field label="Review">
          <select value={leadStatusFilter} onChange={(event) => setLeadStatusFilter(event.target.value)}>
            <option value="">Any review</option>
            {leadStatuses.map((item) => (
              <option value={item} key={item}>{item.replace("_", " ")}</option>
            ))}
          </select>
        </Field>
        <button
          className="secondary"
          type="button"
          onClick={() => {
            setStatus("");
            setHasWebsite("true");
            setHasEmail("false");
            setHasPhone("");
          }}
        >
          Needs enrichment
        </button>
      </section>
      <section className="leads-layout">
        <section className="panel">
          <div className="section-head">
            <div>
              <h2>Stored leads</h2>
              <p>{allLeads.length} matching records</p>
            </div>
            <button className="secondary" type="button" onClick={() => void downloadExportedLeads()}>
              <Download size={17} />
              Export CSV
            </button>
          </div>
          <div className="pagination-bar">
            <div className="pagination-group">
              <span className="label">Rows</span>
              <select
                value={pageSize}
                onChange={(event) => {
                  const value = event.target.value;
                  setPageSize(value === "all" ? "all" : Number(value));
                }}
              >
                <option value={10}>10</option>
                <option value={30}>30</option>
                <option value={50}>50</option>
                <option value={100}>100</option>
                <option value="all">All</option>
              </select>
            </div>
            <div className="pagination-group">
              <button
                className="secondary"
                type="button"
                disabled={currentPage <= 1 || pageSize === "all"}
                onClick={() => setPage((value) => Math.max(1, value - 1))}
              >
                Previous
              </button>
              <span className="page-count">
                Page {currentPage} of {totalPages}
              </span>
              <button
                className="secondary"
                type="button"
                disabled={currentPage >= totalPages || pageSize === "all"}
                onClick={() => setPage((value) => Math.min(totalPages, value + 1))}
              >
                Next
              </button>
            </div>
          </div>
          {leads.isLoading ? (
            <div className="muted">Loading leads...</div>
          ) : leads.isError ? (
            <ErrorAlert error={leads.error} />
          ) : (
            <LeadsTable
              leads={visibleLeads}
              selectedLeadId={selectedLead?.lead_id}
              headerFilters={{
                name: nameColumnFilter,
                businessType: businessTypeColumnFilter,
                searchLocation: searchLocationColumnFilter,
                campaign: campaignColumnFilter,
                businessTypeOptions,
                searchLocationOptions,
                campaignOptions,
                onNameChange: setNameColumnFilter,
                onBusinessTypeChange: setBusinessTypeColumnFilter,
                onSearchLocationChange: setSearchLocationColumnFilter,
                onCampaignChange: setCampaignColumnFilter,
              }}
              onSelectLead={(lead) => {
                setSelectedLead(selectedLead?.lead_id === lead.lead_id ? undefined : lead);
              }}
              onUpdateLeadFlag={(lead, value) => {
                if (!lead.lead_id) return;
                updateLeadReview.mutate(
                  { leadId: lead.lead_id, payload: { lead_flag: value } },
                  { onSuccess: (response) => {
                    if (selectedLead?.lead_id === lead.lead_id) setSelectedLead(response.lead);
                  } },
                );
              }}
              onUpdateLeadStatus={(lead, value) => {
                if (!lead.lead_id) return;
                updateLeadReview.mutate(
                  { leadId: lead.lead_id, payload: { lead_status: value } },
                  { onSuccess: (response) => {
                    if (selectedLead?.lead_id === lead.lead_id) setSelectedLead(response.lead);
                  } },
                );
              }}
              updatingLeadId={updateLeadReview.isPending ? updateLeadReview.variables?.leadId : undefined}
              renderExpandedLead={(lead) => (
                <LeadDetailPanel
                  lead={selectedLead?.lead_id === lead.lead_id ? selectedLead : lead}
                  onLeadUpdated={setSelectedLead}
                />
              )}
              showActions
            />
          )}
        </section>
      </section>
    </>
  );
}

function CampaignStageCounts({
  campaign,
  activeStage,
  onStageChange,
}: {
  campaign: Campaign;
  activeStage: string;
  onStageChange: (stage: string) => void;
}) {
  return (
    <div className="stage-counts">
      <button
        type="button"
        className={`stage-count-button ${activeStage === "" ? "active" : ""}`}
        onClick={() => onStageChange("")}
      >
        All <strong>{campaign.total_leads}</strong>
      </button>
      {campaignStages.map((stage) => (
        <button
          type="button"
          className={`stage-count-button ${activeStage === stage ? "active" : ""}`}
          key={stage}
          onClick={() => onStageChange(stage)}
        >
          {stage.replace("_", " ")} <strong>{Number(campaign[stage as keyof Campaign] ?? 0)}</strong>
        </button>
      ))}
    </div>
  );
}

function CampaignLeadsTable({
  leads,
  selectedCampaignLeadId,
  onSelectLead,
  onUpdate,
  onGenerate,
  businessRules,
  updatingCampaignLeadId,
  generatingCampaignLeadId,
}: {
  leads: CampaignLead[];
  selectedCampaignLeadId?: number;
  onSelectLead: (lead: CampaignLead) => void;
  onUpdate: (lead: CampaignLead, payload: Partial<CampaignLead>) => void;
  onGenerate: (lead: CampaignLead) => void;
  businessRules: BusinessTypeEmailRule[];
  updatingCampaignLeadId?: number;
  generatingCampaignLeadId?: number;
}) {
  if (!leads.length) {
    return <EmptyState title="No campaign leads" body="Adjust filters or create a campaign from matching leads." />;
  }

  return (
    <div className="table-wrap">
      <table className="campaign-leads-table">
        <thead>
          <tr>
            <th>Lead</th>
            <th>Email</th>
            <th>Website</th>
            <th>Flag</th>
            <th>Stage</th>
            <th>Priority</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {leads.map((lead) => {
            const isSelected = selectedCampaignLeadId === lead.campaign_lead_id;
            return (
              <Fragment key={lead.campaign_lead_id}>
                <tr
                  className={[isSelected ? "selected-row" : "", "clickable-row"].join(" ")}
                  onClick={() => onSelectLead(lead)}
                >
                  <td>
                    <strong>{lead.name || "Untitled"}</strong>
                    <span className="muted">{lead.address || lead.location || "-"}</span>
                  </td>
                  <td className="email-cell"><EmailListCell emails={lead.primary_email || lead.emails} /></td>
                  <td className="url-cell">
                    {lead.website ? <a href={lead.website} target="_blank" rel="noreferrer">{lead.website}</a> : "-"}
                  </td>
                  <td><FlagBadge flag={lead.lead_flag} /></td>
                  <td>
                    <select
                      value={lead.stage}
                      disabled={updatingCampaignLeadId === lead.campaign_lead_id}
                      onClick={(event) => event.stopPropagation()}
                      onChange={(event) => onUpdate(lead, { stage: event.target.value })}
                    >
                      {campaignStages.map((stage) => (
                        <option value={stage} key={stage}>{stage.replace("_", " ")}</option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <select
                      value={lead.priority || ""}
                      disabled={updatingCampaignLeadId === lead.campaign_lead_id}
                      onClick={(event) => event.stopPropagation()}
                      onChange={(event) => onUpdate(lead, { priority: event.target.value })}
                    >
                      {campaignPriorities.map((priority) => (
                        <option value={priority} key={priority}>{priority || "None"}</option>
                      ))}
                    </select>
                  </td>
                  <td className="actions-cell">
                    <div className="actions-row">
                      <button
                        className="icon-button"
                        type="button"
                        disabled={!lead.website}
                        title={lead.website ? "Open website" : "No website"}
                        onClick={(event) => {
                          event.stopPropagation();
                          if (lead.website) window.open(lead.website, "_blank", "noopener,noreferrer");
                        }}
                      >
                        <ExternalLink size={15} />
                      </button>
                      <button
                        className="icon-button"
                        type="button"
                        disabled={!canGenerateEmailDraft(lead) || generatingCampaignLeadId === lead.campaign_lead_id}
                        title={canGenerateEmailDraft(lead) ? "Generate email draft" : "Lead is not eligible for generation"}
                        onClick={(event) => {
                          event.stopPropagation();
                          onGenerate(lead);
                        }}
                      >
                        {generatingCampaignLeadId === lead.campaign_lead_id ? <Loader2 className="spin" size={15} /> : <Mail size={15} />}
                      </button>
                      <button
                        className="icon-button"
                        type="button"
                        title="Copy lead"
                        onClick={(event) => {
                          event.stopPropagation();
                          copyToClipboard(formatLeadAsText(lead));
                        }}
                      >
                        <Copy size={15} />
                      </button>
                    </div>
                  </td>
                </tr>
                {isSelected && (
                  <tr className="expanded-detail-row">
                    <td colSpan={7}>
                      <CampaignLeadDetail
                        lead={lead}
                        onUpdate={onUpdate}
                        onGenerate={onGenerate}
                        businessRule={businessRules.find((rule) => rule.business_type === lead.business_type)}
                        isGenerating={generatingCampaignLeadId === lead.campaign_lead_id}
                      />
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function CampaignLeadDetail({
  lead,
  onUpdate,
  onGenerate,
  businessRule,
  isGenerating,
}: {
  lead: CampaignLead;
  onUpdate: (lead: CampaignLead, payload: Partial<CampaignLead>) => void;
  onGenerate: (lead: CampaignLead) => void;
  businessRule?: BusinessTypeEmailRule;
  isGenerating?: boolean;
}) {
  const [campaignNotes, setCampaignNotes] = useState(lead.campaign_notes ?? "");
  const [emailDraft, setEmailDraft] = useState(lead.email_draft ?? "");
  const [finalEmail, setFinalEmail] = useState(lead.final_email ?? "");

  useEffect(() => {
    setCampaignNotes(lead.campaign_notes ?? "");
    setEmailDraft(lead.email_draft ?? "");
    setFinalEmail(lead.final_email ?? "");
  }, [lead]);

  return (
    <section className="panel">
      <div className="detail-grid">
        <div>
          <span className="label">Phone</span>
          <strong>{lead.phone || "-"}</strong>
        </div>
        <div>
          <span className="label">Primary email</span>
          <strong>{lead.primary_email || lead.emails || "-"}</strong>
        </div>
        <div>
          <span className="label">Lead review</span>
          <strong>{lead.lead_status || "-"}</strong>
        </div>
        <div>
          <span className="label">Contacted</span>
          <strong>{lead.contacted_at || "-"}</strong>
        </div>
        <div className="detail-wide">
          <span className="label">Website context</span>
          <p className="context-text">{lead.website_summary || "No captured website context."}</p>
        </div>
        <div className="detail-wide">
          <span className="label">Business-type rule</span>
          <p className="context-text">
            {businessRule
              ? [businessRule.business_description, businessRule.pain_point, businessRule.offer_angle, businessRule.extra_instructions].filter(Boolean).join(" ")
              : "No business-type rule configured."}
          </p>
        </div>
      </div>
      <div className="campaign-edit-grid">
        <Field label="Campaign notes">
          <AutoResizeTextarea value={campaignNotes} onChange={(event) => setCampaignNotes(event.target.value)} />
        </Field>
        <Field label="Email draft">
          <div className="copyable-field">
            <AutoResizeTextarea value={emailDraft} onChange={(event) => setEmailDraft(event.target.value)} />
            <button
              type="button"
              className="secondary"
              disabled={!emailDraft.trim()}
              onClick={() => copyToClipboard(emailDraft)}
            >
              <Copy size={17} />
              Copy draft
            </button>
          </div>
        </Field>
        <Field label="Final email">
          <div className="copyable-field">
            <AutoResizeTextarea value={finalEmail} onChange={(event) => setFinalEmail(event.target.value)} />
            <button
              type="button"
              className="secondary"
              disabled={!finalEmail.trim()}
              onClick={() => copyToClipboard(finalEmail)}
            >
              <Copy size={17} />
              Copy final
            </button>
          </div>
        </Field>
      </div>
      <div className="button-row">
        <button
          type="button"
          className="secondary"
          disabled={!canGenerateEmailDraft(lead) || isGenerating}
          onClick={() => onGenerate(lead)}
        >
          {isGenerating ? <Loader2 className="spin" size={17} /> : <Mail size={17} />}
          Generate draft
        </button>
        <button
          type="button"
          className="secondary"
          onClick={() => onUpdate(lead, {
            campaign_notes: campaignNotes,
            email_draft: emailDraft,
            final_email: finalEmail,
          })}
        >
          <CheckCircle2 size={17} />
          Save campaign fields
        </button>
        <button
          type="button"
          className="secondary"
          disabled={!finalEmail.trim()}
          onClick={() => onUpdate(lead, {
            final_email: finalEmail,
            stage: "approved",
          })}
        >
          <CheckCircle2 size={17} />
          Approve final
        </button>
        <button
          type="button"
          className="secondary"
          onClick={() => onUpdate(lead, {
            stage: "contacted",
            contacted_at: new Date().toISOString(),
          })}
        >
          <Mail size={17} />
          Mark contacted
        </button>
      </div>
    </section>
  );
}

function CampaignsPage() {
  const campaigns = useCampaigns();
  const createCampaign = useCreateCampaign();
  const updateCampaign = useUpdateCampaign();
  const updateCampaignLead = useUpdateCampaignLead();
  const generateCampaignLeadEmail = useGenerateCampaignLeadEmail();
  const generateCampaignEmails = useGenerateCampaignEmails();
  const businessRules = useBusinessTypeEmailRules();
  const { searchParams, setParam, setParams } = useUrlState();
  const selectedCampaignId = getSearchNumber(searchParams, "campaign_id", 0) || undefined;
  const selectedCampaignLeadId = getSearchNumber(searchParams, "campaign_lead_id", 0) || undefined;
  const [name, setName] = useSessionStorageState("scraping-console:campaign-draft-name", "");
  const businessType = getSearchString(searchParams, "business_type");
  const searchLocation = getSearchString(searchParams, "search_location");
  const statusFilter = getSearchString(searchParams, "lead_status", "scraped");
  const hasEmail = getSearchBooleanString(searchParams, "has_email", "true");
  const hasWebsite = getSearchBooleanString(searchParams, "has_website");
  const hasPhone = getSearchBooleanString(searchParams, "has_phone");
  const leadFlagFilter = getSearchString(searchParams, "lead_flag");
  const leadStatusFilter = getSearchString(searchParams, "review_status");
  const [notes, setNotes] = useSessionStorageState("scraping-console:campaign-draft-notes", "");
  const stageFilter = getSearchString(searchParams, "stage");
  const campaignSearch = getSearchString(searchParams, "search");
  const setSelectedCampaignId = (value?: number) => setParam("campaign_id", value ?? "", { replace: false });
  const setSelectedCampaignLeadId = (value?: number) => setParam("campaign_lead_id", value ?? "", { replace: false });
  const selectCampaign = (campaignId: number) => {
    setParams({ campaign_id: campaignId, campaign_lead_id: "" }, { replace: false });
  };
  const selectStage = (stage: string) => {
    setParams({ stage, campaign_lead_id: "" });
  };
  const setBusinessType = (value: string) => setParam("business_type", value);
  const setSearchLocation = (value: string) => setParam("search_location", value);
  const setStatusFilter = (value: string) => setParam("lead_status", value);
  const setHasEmail = (value: string) => setParam("has_email", value);
  const setHasWebsite = (value: string) => setParam("has_website", value);
  const setHasPhone = (value: string) => setParam("has_phone", value);
  const setLeadFlagFilter = (value: string) => setParam("lead_flag", value);
  const setLeadStatusFilter = (value: string) => setParam("review_status", value);
  const setStageFilter = (value: string) => setParam("stage", value);
  const setCampaignSearch = (value: string) => setParam("search", value);
  const leadFilterOptions = useLeadFilterOptions();
  const allLeadOptions = useLeads({});
  const campaignFilters = useMemo(() => ({
    status: statusFilter || undefined,
    has_email: hasEmail === "" ? undefined : hasEmail === "true",
    has_website: hasWebsite === "" ? undefined : hasWebsite === "true",
    has_phone: hasPhone === "" ? undefined : hasPhone === "true",
    lead_flag: leadFlagFilter || undefined,
    lead_status: leadStatusFilter || undefined,
    business_type: businessType || undefined,
    search_location: searchLocation || undefined,
  }), [businessType, hasEmail, hasPhone, hasWebsite, leadFlagFilter, leadStatusFilter, searchLocation, statusFilter]);
  const derivedLeadFilterOptions = useMemo(() => {
    const businessTypeCounts = new Map<string, number>();
    const searchLocationCounts = new Map<string, number>();
    const pairCounts = new Map<string, number>();

    (allLeadOptions.data?.leads ?? []).forEach((lead) => {
      const parsed = parseLeadLocation(lead.location);
      if (parsed.businessType) {
        businessTypeCounts.set(parsed.businessType, (businessTypeCounts.get(parsed.businessType) ?? 0) + 1);
      }
      if (parsed.searchLocation) {
        searchLocationCounts.set(parsed.searchLocation, (searchLocationCounts.get(parsed.searchLocation) ?? 0) + 1);
      }
      if (parsed.businessType && parsed.searchLocation) {
        const key = `${parsed.businessType}\u0000${parsed.searchLocation}`;
        pairCounts.set(key, (pairCounts.get(key) ?? 0) + 1);
      }
    });

    return {
      business_types: [...businessTypeCounts.entries()]
        .map(([value, count]) => ({ value, count }))
        .sort((a, b) => a.value.localeCompare(b.value)),
      search_locations: [...searchLocationCounts.entries()]
        .map(([value, count]) => ({ value, count }))
        .sort((a, b) => a.value.localeCompare(b.value)),
      pairs: [...pairCounts.entries()]
        .map(([key, count]) => {
          const [business_type, search_location] = key.split("\u0000");
          return { business_type, search_location, count };
        })
        .sort((a, b) => (
          a.business_type.localeCompare(b.business_type) ||
          a.search_location.localeCompare(b.search_location)
        )),
    };
  }, [allLeadOptions.data?.leads]);
  const effectiveLeadFilterOptions = useMemo(() => {
    const options = leadFilterOptions.data;
    const hasCountedOptions = Boolean(options?.pairs?.length);
    return hasCountedOptions ? options : derivedLeadFilterOptions;
  }, [derivedLeadFilterOptions, leadFilterOptions.data]);
  const filteredBusinessTypeOptions = useMemo(() => {
    const options = effectiveLeadFilterOptions;
    if (!options) return [];
    if (!searchLocation) {
      return options.business_types
        .map(normalizeCountOption)
        .filter((item): item is { value: string; count: number } => Boolean(item));
    }

    return options.pairs
      .filter((pair) => (
        pair.search_location === searchLocation &&
        typeof pair.business_type === "string" &&
        pair.business_type.trim()
      ))
      .map((pair) => ({
        value: pair.business_type,
        count: pair.count,
      }))
      .sort((a, b) => a.value.localeCompare(b.value));
  }, [effectiveLeadFilterOptions, searchLocation]);
  const filteredLocationOptions = useMemo(() => {
    const options = effectiveLeadFilterOptions;
    if (!options) return [];
    if (!businessType) {
      return options.search_locations
        .map(normalizeCountOption)
        .filter((item): item is { value: string; count: number } => Boolean(item));
    }

    return options.pairs
      .filter((pair) => (
        pair.business_type === businessType &&
        typeof pair.search_location === "string" &&
        pair.search_location.trim()
      ))
      .map((pair) => ({
        value: pair.search_location,
        count: pair.count,
      }))
      .sort((a, b) => a.value.localeCompare(b.value));
  }, [businessType, effectiveLeadFilterOptions]);
  const previewLeads = useLeads(campaignFilters);

  useEffect(() => {
    if (!businessType) return;
    const isValid = filteredBusinessTypeOptions.some((item) => item.value === businessType);
    if (!isValid) setBusinessType("");
  }, [businessType, filteredBusinessTypeOptions]);

  useEffect(() => {
    if (!searchLocation) return;
    const isValid = filteredLocationOptions.some((item) => item.value === searchLocation);
    if (!isValid) setSearchLocation("");
  }, [filteredLocationOptions, searchLocation]);

  const selectedCampaign = campaigns.data?.campaigns.find((campaign) => campaign.campaign_id === selectedCampaignId);
  const campaign = useCampaign(selectedCampaignId);
  const campaignLeads = useCampaignLeads(selectedCampaignId, {
    stage: stageFilter || undefined,
    search: campaignSearch || undefined,
  });
  const activeCampaign = campaign.data?.campaign ?? selectedCampaign;

  function submitCampaign(event: FormEvent) {
    event.preventDefault();
    createCampaign.mutate({
      name,
      notes,
      filters: campaignFilters,
    }, {
      onSuccess: (response) => {
        setSelectedCampaignId(response.campaign.campaign_id);
        setName("");
        setNotes("");
      },
    });
  }

  return (
    <>
      <PageHeader
        title="Campaigns"
        description="Create working lists from filtered leads and track outreach-specific stages."
      />
      <section className="campaigns-layout">
        <section className="panel">
          <div className="section-head">
            <div>
              <h2>Campaign list</h2>
              <p>{campaigns.data?.count ?? 0} campaigns</p>
            </div>
          </div>
          {campaigns.isLoading ? (
            <div className="muted">Loading campaigns...</div>
          ) : campaigns.isError ? (
            <ErrorAlert error={campaigns.error} />
          ) : !campaigns.data?.campaigns.length ? (
            <EmptyState title="No campaigns yet" body="Create one from lead filters to start a curated workflow." />
          ) : (
            <div className="campaign-list">
              {campaigns.data.campaigns.map((item) => (
                <button
                  type="button"
                  className={`campaign-list-item ${selectedCampaignId === item.campaign_id ? "active" : ""}`}
                  key={item.campaign_id}
                  onClick={() => selectCampaign(item.campaign_id)}
                >
                  <span>
                    <strong>{item.name}</strong>
                    <small>{item.business_type || "-"} / {item.search_location || "-"}</small>
                  </span>
                  <StatusBadge status={item.status} />
                  <span className="muted">{item.total_leads} leads</span>
                </button>
              ))}
            </div>
          )}
        </section>
        <section className="panel">
          <div className="section-head">
            <div>
              <h2>Create campaign</h2>
              <p>
                {previewLeads.isLoading
                  ? "Checking matching leads..."
                  : `${previewLeads.data?.count ?? 0} matching leads`}
              </p>
            </div>
          </div>
          <form className="campaign-create-form" onSubmit={submitCampaign}>
            <Field label="Name">
              <input value={name} onChange={(event) => setName(event.target.value)} placeholder="Dentists London May 2026" />
            </Field>
            <Field label="Business type">
              <select
                value={businessType}
                onChange={(event) => setBusinessType(event.target.value)}
                disabled={leadFilterOptions.isLoading && allLeadOptions.isLoading}
              >
                <option value="">Any business type</option>
                {filteredBusinessTypeOptions.map((item) => (
                  <option value={item.value} key={item.value}>
                    {optionLabel(item)}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Location">
              <select
                value={searchLocation}
                onChange={(event) => setSearchLocation(event.target.value)}
                disabled={leadFilterOptions.isLoading && allLeadOptions.isLoading}
              >
                <option value="">Any location</option>
                {filteredLocationOptions.map((item) => (
                  <option value={item.value} key={item.value}>
                    {optionLabel(item)}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Scrape status">
              <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
                <option value="">Any</option>
                <option value="scraped">Scraped</option>
                <option value="failed">Failed</option>
                <option value="skipped">Skipped</option>
                <option value="pending">Pending</option>
              </select>
            </Field>
            <Field label="Email">
              <select value={hasEmail} onChange={(event) => setHasEmail(event.target.value)}>
                <option value="">Any</option>
                <option value="true">Has email</option>
                <option value="false">No email</option>
              </select>
            </Field>
            <Field label="Website">
              <select value={hasWebsite} onChange={(event) => setHasWebsite(event.target.value)}>
                <option value="">Any</option>
                <option value="true">Has website</option>
                <option value="false">No website</option>
              </select>
            </Field>
            <Field label="Phone">
              <select value={hasPhone} onChange={(event) => setHasPhone(event.target.value)}>
                <option value="">Any</option>
                <option value="true">Has phone</option>
                <option value="false">No phone</option>
              </select>
            </Field>
            <Field label="Flag">
              <select value={leadFlagFilter} onChange={(event) => setLeadFlagFilter(event.target.value)}>
                <option value="">Any</option>
                {leadFlags.map((flag) => <option value={flag} key={flag}>{flag.replace("_", " ")}</option>)}
              </select>
            </Field>
            <Field label="Review">
              <select value={leadStatusFilter} onChange={(event) => setLeadStatusFilter(event.target.value)}>
                <option value="">Any</option>
                {leadStatuses.map((item) => <option value={item} key={item}>{item.replace("_", " ")}</option>)}
              </select>
            </Field>
            <Field label="Notes" className="detail-wide">
              <AutoResizeTextarea value={notes} onChange={(event) => setNotes(event.target.value)} />
            </Field>
            <button type="submit" disabled={createCampaign.isPending || !name.trim()}>
              {createCampaign.isPending ? <Loader2 className="spin" size={17} /> : <Megaphone size={17} />}
              Create campaign
            </button>
            <ErrorAlert error={createCampaign.error} />
            {createCampaign.data && (
              <div className="alert">
                Added {createCampaign.data.added_leads} leads to {createCampaign.data.campaign.name}.
              </div>
            )}
          </form>
        </section>
      </section>

      {activeCampaign && (
        <section className="panel campaign-detail">
          <div className="section-head">
            <div>
              <h2>{activeCampaign.name}</h2>
              <p>{activeCampaign.business_type || "-"} / {activeCampaign.search_location || "-"} / {activeCampaign.total_leads} leads</p>
            </div>
            <div className="topbar-actions">
              <select
                value={activeCampaign.status}
                onChange={(event) => updateCampaign.mutate({
                  campaignId: activeCampaign.campaign_id,
                  payload: { status: event.target.value },
                })}
              >
                {campaignStatuses.map((item) => <option value={item} key={item}>{item}</option>)}
              </select>
              <button
                className="secondary"
                type="button"
                disabled={generateCampaignEmails.isPending}
                onClick={() => generateCampaignEmails.mutate({
                  campaignId: activeCampaign.campaign_id,
                  payload: {
                    stage: stageFilter || undefined,
                    search: campaignSearch || undefined,
                    limit: 25,
                  },
                })}
              >
                {generateCampaignEmails.isPending ? <Loader2 className="spin" size={17} /> : <Mail size={17} />}
                Generate visible drafts
              </button>
              <button
                className="secondary"
                type="button"
                onClick={() => void downloadCampaignExport(activeCampaign.campaign_id, stageFilter || undefined)}
              >
                <Download size={17} />
                Export
              </button>
            </div>
          </div>
          <CampaignStageCounts
            campaign={activeCampaign}
            activeStage={stageFilter}
            onStageChange={selectStage}
          />
          <div className="campaign-toolbar">
            <Field label="Search">
              <input value={campaignSearch} onChange={(event) => setCampaignSearch(event.target.value)} placeholder="Name, address, email" />
            </Field>
          </div>
          {campaignLeads.isLoading ? (
            <div className="muted">Loading campaign leads...</div>
          ) : campaignLeads.isError ? (
            <ErrorAlert error={campaignLeads.error} />
          ) : (
            <CampaignLeadsTable
              leads={campaignLeads.data?.leads ?? []}
              selectedCampaignLeadId={selectedCampaignLeadId}
              onSelectLead={(lead) => setSelectedCampaignLeadId(selectedCampaignLeadId === lead.campaign_lead_id ? undefined : lead.campaign_lead_id)}
              onUpdate={(lead, payload) => updateCampaignLead.mutate({
                campaignId: lead.campaign_id,
                campaignLeadId: lead.campaign_lead_id,
                payload: {
                  stage: payload.stage,
                  priority: payload.priority ?? undefined,
                  email_draft: payload.email_draft ?? undefined,
                  final_email: payload.final_email ?? undefined,
                  campaign_notes: payload.campaign_notes ?? undefined,
                  contacted_at: payload.contacted_at ?? undefined,
                },
              })}
              onGenerate={(lead) => generateCampaignLeadEmail.mutate({
                campaignId: lead.campaign_id,
                campaignLeadId: lead.campaign_lead_id,
              })}
              businessRules={businessRules.data?.rules ?? []}
              updatingCampaignLeadId={updateCampaignLead.isPending ? updateCampaignLead.variables?.campaignLeadId : undefined}
              generatingCampaignLeadId={generateCampaignLeadEmail.isPending ? generateCampaignLeadEmail.variables?.campaignLeadId : undefined}
            />
          )}
          <ErrorAlert error={updateCampaign.error || updateCampaignLead.error || generateCampaignLeadEmail.error || generateCampaignEmails.error} />
          {generateCampaignEmails.data && (
            <div className="alert">
              Generated {generateCampaignEmails.data.generated_count} drafts. Skipped {generateCampaignEmails.data.skipped_count}; errors {generateCampaignEmails.data.error_count}.
            </div>
          )}
        </section>
      )}
    </>
  );
}

function EmailRulesPage() {
  const rules = useEmailCategoryRules();
  const unknowns = useUnknownEmailLocalParts();
  const updateRule = useUpdateEmailCategoryRule();
  const applyRules = useApplyEmailCategoryRules();
  const [selectedCategoryByPattern, setSelectedCategoryByPattern] = useState<Record<string, string>>({});
  const [manualPattern, setManualPattern] = useState("");
  const [manualCategory, setManualCategory] = useState("");

  const categories = useMemo(
    () => (rules.data?.categories ?? emailCategories).filter((category) => category !== "unknown"),
    [rules.data?.categories],
  );

  function categoryForPattern(pattern: string) {
    return selectedCategoryByPattern[pattern] ?? "";
  }

  function saveRule(pattern: string, category: string) {
    updateRule.mutate({ pattern, payload: { category, is_active: true } });
  }

  return (
    <>
      <PageHeader
        title="Email Rules"
        description="Manage exact local-part rules for automatically categorizing scraped emails."
      />
      <section className="email-rules-layout">
        <section className="panel">
          <div className="section-head">
            <div>
              <h2>Unknown local-parts</h2>
              <p>{unknowns.data?.count ?? 0} unresolved patterns</p>
            </div>
            <button
              type="button"
              className="secondary"
              disabled={applyRules.isPending}
              onClick={() => applyRules.mutate()}
            >
              {applyRules.isPending ? <Loader2 className="spin" size={17} /> : <RotateCw size={17} />}
              Reapply rules
            </button>
          </div>
          {unknowns.isLoading ? (
            <div className="muted">Loading unknown emails...</div>
          ) : unknowns.isError ? (
            <ErrorAlert error={unknowns.error} />
          ) : !unknowns.data?.local_parts.length ? (
            <EmptyState title="No unknown email patterns" body="New unknown local-parts will appear here after scraping or manual email entry." />
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Local part</th>
                    <th>Example</th>
                    <th>Count</th>
                    <th>Category</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {unknowns.data.local_parts.map((item) => (
                    <tr key={item.local_part}>
                      <td><strong>{item.local_part}</strong></td>
                      <td className="email-cell"><EmailListCell emails={item.example_email} /></td>
                      <td>{item.count}</td>
                      <td>
                        <select
                          value={categoryForPattern(item.local_part)}
                          onChange={(event) => setSelectedCategoryByPattern((current) => ({
                            ...current,
                            [item.local_part]: event.target.value,
                          }))}
                        >
                          <option value="">Choose category</option>
                          {categories.map((category) => (
                            <option value={category} key={category}>{category}</option>
                          ))}
                        </select>
                      </td>
                      <td>
                        <button
                          type="button"
                          className="secondary"
                          disabled={updateRule.isPending || !categoryForPattern(item.local_part)}
                          onClick={() => saveRule(item.local_part, categoryForPattern(item.local_part))}
                        >
                          <CheckCircle2 size={17} />
                          Add rule
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {applyRules.data && (
            <div className="alert">
              Updated {applyRules.data.updated_count} unknown email rows.
            </div>
          )}
        </section>
        <section className="panel">
          <div className="section-head">
            <div>
              <h2>Active rules</h2>
              <p>{rules.data?.count ?? 0} exact local-part rules</p>
            </div>
          </div>
          <div className="settings-form">
            <Field label="Local part">
              <input value={manualPattern} onChange={(event) => setManualPattern(event.target.value)} placeholder="reservation" />
            </Field>
            <Field label="Category">
              <select value={manualCategory} onChange={(event) => setManualCategory(event.target.value)}>
                <option value="">Choose category</option>
                {categories.map((category) => (
                  <option value={category} key={category}>{category}</option>
                ))}
              </select>
            </Field>
            <button
              type="button"
              disabled={!manualPattern.trim() || !manualCategory || updateRule.isPending}
              onClick={() => {
                saveRule(manualPattern, manualCategory);
                setManualPattern("");
                setManualCategory("");
              }}
            >
              {updateRule.isPending ? <Loader2 className="spin" size={17} /> : <CheckCircle2 size={17} />}
              Save rule
            </button>
          </div>
          {rules.isLoading ? (
            <div className="muted">Loading rules...</div>
          ) : rules.isError ? (
            <ErrorAlert error={rules.error} />
          ) : (
            <div className="rule-list">
              {(rules.data?.rules ?? []).map((rule) => (
                <span className="chip" key={`${rule.match_type}-${rule.pattern}`}>
                  {`${rule.pattern} -> ${rule.category}${rule.is_active ? "" : " inactive"}`}
                </span>
              ))}
            </div>
          )}
          <ErrorAlert error={updateRule.error || applyRules.error} />
        </section>
      </section>
    </>
  );
}

function SettingsBusinessRuleEditor({
  businessTypes,
  rules,
  onSave,
  isSaving,
}: {
  businessTypes: Array<{ value: string; count: number }>;
  rules: BusinessTypeEmailRule[];
  onSave: (businessType: string, payload: {
    business_description: string;
    pain_point: string;
    offer_angle: string;
    extra_instructions: string;
  }) => void;
  isSaving?: boolean;
}) {
  const [selectedBusinessType, setSelectedBusinessType] = useState("");
  const selectedRule = rules.find((rule) => rule.business_type === selectedBusinessType);
  const [businessDescription, setBusinessDescription] = useState("");
  const [painPoint, setPainPoint] = useState("");
  const [offerAngle, setOfferAngle] = useState("");
  const [extraInstructions, setExtraInstructions] = useState("");

  useEffect(() => {
    setBusinessDescription(selectedRule?.business_description ?? "");
    setPainPoint(selectedRule?.pain_point ?? "");
    setOfferAngle(selectedRule?.offer_angle ?? "");
    setExtraInstructions(selectedRule?.extra_instructions ?? "");
  }, [selectedRule]);

  useEffect(() => {
    if (!selectedBusinessType && businessTypes.length) {
      setSelectedBusinessType(businessTypes[0].value);
    }
  }, [businessTypes, selectedBusinessType]);

  return (
    <section className="panel">
      <div className="section-head">
        <div>
          <h2>Business-type personalization</h2>
          <p>{rules.length} configured rules</p>
        </div>
      </div>
      <div className="settings-form">
        <Field label="Business type">
          <select value={selectedBusinessType} onChange={(event) => setSelectedBusinessType(event.target.value)}>
            {!businessTypes.length && <option value="">No business types found</option>}
            {businessTypes.map((item) => (
              <option value={item.value} key={item.value}>{optionLabel(item)}</option>
            ))}
          </select>
        </Field>
        <Field label="Specific description">
          <input value={businessDescription} onChange={(event) => setBusinessDescription(event.target.value)} />
        </Field>
        <Field label="Specific problem">
          <input value={painPoint} onChange={(event) => setPainPoint(event.target.value)} />
        </Field>
        <Field label="Offer angle">
          <input value={offerAngle} onChange={(event) => setOfferAngle(event.target.value)} />
        </Field>
        <Field label="Extra instructions" className="detail-wide">
          <AutoResizeTextarea value={extraInstructions} onChange={(event) => setExtraInstructions(event.target.value)} />
        </Field>
        <button
          type="button"
          disabled={!selectedBusinessType || isSaving}
          onClick={() => onSave(selectedBusinessType, {
            business_description: businessDescription,
            pain_point: painPoint,
            offer_angle: offerAngle,
            extra_instructions: extraInstructions,
          })}
        >
          {isSaving ? <Loader2 className="spin" size={17} /> : <CheckCircle2 size={17} />}
          Save business rule
        </button>
      </div>
    </section>
  );
}

function SettingsPage() {
  const emailSettings = useEmailSettings();
  const updateEmailSettings = useUpdateEmailSettings();
  const leadFilterOptions = useLeadFilterOptions();
  const businessRules = useBusinessTypeEmailRules();
  const updateBusinessRule = useUpdateBusinessTypeEmailRule();
  const [provider, setProvider] = useState("openai");
  const [model, setModel] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [userPrompt, setUserPrompt] = useState("");

  useEffect(() => {
    if (!emailSettings.data?.settings) return;
    setProvider(emailSettings.data.settings.provider);
    setModel(emailSettings.data.settings.model);
    setSystemPrompt(emailSettings.data.settings.system_prompt);
    setUserPrompt(emailSettings.data.settings.user_prompt);
  }, [emailSettings.data?.settings]);

  return (
    <>
      <PageHeader
        title="Settings"
        description="AI drafting defaults and business-type personalization for campaign outreach."
      />
      <section className="panel">
        <div className="section-head">
          <div>
            <h2>AI email drafting</h2>
            <p>{emailSettings.data?.settings.api_key_configured ? "Provider API key configured" : "Provider API key missing in .env"}</p>
          </div>
        </div>
        {emailSettings.isLoading ? (
          <div className="muted">Loading email settings...</div>
        ) : emailSettings.isError ? (
          <ErrorAlert error={emailSettings.error} />
        ) : (
          <div className="settings-form">
            <Field label="Provider">
              <select value={provider} onChange={(event) => setProvider(event.target.value)}>
                <option value="openai">OpenAI</option>
                <option value="anthropic">Anthropic</option>
              </select>
            </Field>
            <Field label="Model">
              <input value={model} onChange={(event) => setModel(event.target.value)} placeholder="gpt-4o-mini" />
            </Field>
            <Field label="System prompt" className="detail-wide">
              <AutoResizeTextarea value={systemPrompt} onChange={(event) => setSystemPrompt(event.target.value)} />
            </Field>
            <Field label="User prompt / template" className="detail-wide">
              <AutoResizeTextarea value={userPrompt} onChange={(event) => setUserPrompt(event.target.value)} />
            </Field>
            <button
              type="button"
              disabled={updateEmailSettings.isPending || !model.trim() || !systemPrompt.trim() || !userPrompt.trim()}
              onClick={() => updateEmailSettings.mutate({
                provider: provider === "anthropic" ? "anthropic" : "openai",
                model,
                system_prompt: systemPrompt,
                user_prompt: userPrompt,
              })}
            >
              {updateEmailSettings.isPending ? <Loader2 className="spin" size={17} /> : <CheckCircle2 size={17} />}
              Save email settings
            </button>
            <ErrorAlert error={updateEmailSettings.error} />
          </div>
        )}
      </section>
      <SettingsBusinessRuleEditor
        businessTypes={(leadFilterOptions.data?.business_types ?? []).map(normalizeCountOption).filter((item): item is { value: string; count: number } => Boolean(item))}
        rules={businessRules.data?.rules ?? []}
        isSaving={updateBusinessRule.isPending}
        onSave={(businessType, payload) => updateBusinessRule.mutate({ businessType, payload })}
      />
      <ErrorAlert error={leadFilterOptions.error || businessRules.error || updateBusinessRule.error} />
    </>
  );
}

export function App() {
  const [sidebarCollapsed, setSidebarCollapsed] = useLocalStorageState("scraping-console:sidebar-collapsed", false);
  const health = useBackendHealth();
  const queryClient = useQueryClient();

  return (
    <div className={`app-shell ${sidebarCollapsed ? "sidebar-collapsed" : ""}`}>
      <aside className="sidebar">
        <button
          className="sidebar-toggle"
          type="button"
          title={sidebarCollapsed ? "Expand navigation" : "Collapse navigation"}
          onClick={() => setSidebarCollapsed((collapsed) => !collapsed)}
        >
          {sidebarCollapsed ? <Menu size={18} /> : <X size={18} />}
        </button>
        <div className="brand">
          <div className="brand-mark">SC</div>
          <div className="brand-text">
            <strong>Scraping Console</strong>
            <span>Lead operations</span>
          </div>
        </div>
        <nav>
          {pages.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.id}
                to={pagePaths[item.id]}
                className={({ isActive }) => isActive ? "active" : ""}
                title={item.label}
              >
                <Icon size={18} />
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </nav>
      </aside>
      <main>
        <div className="topbar">
          <span className="muted">Local Flask backend</span>
          <div className="topbar-actions">
            <button
              className="secondary"
              type="button"
              onClick={() => void queryClient.invalidateQueries()}
            >
              <RotateCw size={16} />
              Refresh
            </button>
            {health.isSuccess ? <StatusBadge status={health.data.status} /> : <StatusBadge />}
          </div>
        </div>
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/discover" element={<DiscoverPage />} />
          <Route path="/website-emails" element={<WebsiteEmailPage />} />
          <Route path="/enrich" element={<EnrichPage />} />
          <Route path="/leads" element={<LeadsPage />} />
          <Route path="/campaigns" element={<CampaignsPage />} />
          <Route path="/email-rules" element={<EmailRulesPage />} />
          <Route path="/jobs" element={<JobsPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </main>
    </div>
  );
}
