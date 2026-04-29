import { useEffect, useMemo, useState } from "react";
import type { FormEvent, ReactNode } from "react";
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
  Loader2,
  Mail,
  Phone,
  Play,
  RotateCw,
  Search,
  Settings,
  Square,
  Table2,
} from "lucide-react";
import { ApiError, type JobExecution, type JobStatus, type JobStepId, type Lead } from "./api";
import {
  useBackendHealth,
  useGoogleMapsScrape,
  useJobPolling,
  useJobs,
  useLeads,
  useLeadEmailEnrichment,
  useStopJob,
  useSummary,
  useUpdateLead,
  useWebsiteEmailScrape,
} from "./hooks";
import { downloadExportedLeads } from "./hooks";

type PageId = "dashboard" | "discover" | "website" | "enrich" | "leads" | "jobs" | "settings";

const pages: Array<{ id: PageId; label: string; icon: typeof Activity }> = [
  { id: "dashboard", label: "Dashboard", icon: Activity },
  { id: "discover", label: "Find Businesses", icon: Building2 },
  { id: "website", label: "Website Emails", icon: Globe2 },
  { id: "enrich", label: "Enrich Leads", icon: Mail },
  { id: "leads", label: "Leads", icon: Table2 },
  { id: "jobs", label: "Jobs", icon: ClipboardList },
  { id: "settings", label: "Settings", icon: Settings },
];

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
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
    </label>
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

function LeadsTable({
  leads,
  selectedLeadId,
  onSelectLead,
  showActions = false,
}: {
  leads: Lead[];
  selectedLeadId?: number;
  onSelectLead?: (lead: Lead) => void;
  showActions?: boolean;
}) {
  if (!leads.length) {
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
            <th>Name</th>
            <th>Location</th>
            <th>Phone</th>
            <th>Website</th>
            <th>Emails</th>
            <th>Status</th>
            {showActions && <th>Actions</th>}
          </tr>
        </thead>
        <tbody>
          {leads.map((lead, index) => (
            <tr
              key={`${lead.place_id ?? lead.lead_id ?? index}-${index}`}
              className={[
                selectedLeadId === lead.lead_id ? "selected-row" : "",
                onSelectLead ? "clickable-row" : "",
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
              <td>{lead.status ? <StatusBadge status={lead.status} /> : "-"}</td>
              {showActions && (
                <td className="actions-cell">
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
                </td>
              )}
            </tr>
          ))}
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
}: {
  jobs: JobExecution[];
  selectedJobId?: string;
  onSelectJob?: (job: JobExecution) => void;
  onStopJob?: (jobId: string) => void;
  stoppingJobId?: string;
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
          {jobs.map((job) => (
            <tr
              key={`${job.execution_id}-${job.job_id}`}
              className={[
                selectedJobId === job.job_id ? "selected-row" : "",
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
                    <button className="text-button" type="button" onClick={() => onSelectJob(job)}>
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
          ))}
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
  const [location, setLocation] = useState("");
  const [placeType, setPlaceType] = useState("lodging");
  const [maxPlaces, setMaxPlaces] = useState(20);

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
  const [url, setUrl] = useState("");
  const [maxPages, setMaxPages] = useState(10);
  const [sitemapLimit, setSitemapLimit] = useState(10);
  const [headless, setHeadless] = useState(true);
  const [useTor, setUseTor] = useState(false);

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

  if (!jobId) {
    return (
      <section className="panel">
        <EmptyState title="No job selected" body="Select a job from the table to inspect its current progress." />
      </section>
    );
  }

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
  const [status, setStatus] = useState("");
  const [stepId, setStepId] = useState("");
  const [limit, setLimit] = useState(50);
  const [selectedJobId, setSelectedJobId] = useState<string>();
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
      <section className="grid jobs-layout">
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
              onSelectJob={(job) => setSelectedJobId(job.job_id)}
              onStopJob={(jobId) => stop.mutate(jobId)}
              stoppingJobId={stop.isPending ? stop.variables : undefined}
            />
          )}
        </section>
        <JobDetailPanel jobId={selectedJobId} />
      </section>
    </>
  );
}

function EnrichPage() {
  const enrich = useLeadEmailEnrichment();
  const [jobId, setJobId] = useState<string>();
  const [maxPages, setMaxPages] = useState(30);
  const [headless, setHeadless] = useState(true);
  const [useTor, setUseTor] = useState(false);

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

function LeadDetailPanel({
  lead,
  onLeadUpdated,
}: {
  lead?: Lead;
  onLeadUpdated?: (lead: Lead) => void;
}) {
  const updateLead = useUpdateLead();
  const [website, setWebsite] = useState("");
  const [emails, setEmails] = useState("");
  const [status, setStatus] = useState("");

  useEffect(() => {
    setWebsite(lead?.website ?? "");
    setEmails(lead?.emails ?? "");
    setStatus(lead?.status ?? "");
  }, [lead]);

  if (!lead) {
    return (
      <section className="panel">
        <EmptyState title="No lead selected" body="Select a row to inspect and edit lead details." />
      </section>
    );
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!lead?.lead_id) return;
    updateLead.mutate({
      leadId: lead.lead_id,
      payload: {
        website,
        emails,
        status,
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
          <p>{lead.address || lead.location || "No location"}</p>
        </div>
        {lead.status && <StatusBadge status={lead.status} />}
      </div>
      <div className="detail-grid">
        <div>
          <span className="label">Phone</span>
          <strong>{lead.phone || "-"}</strong>
        </div>
        <div>
          <span className="label">Source job</span>
          <strong className="mono">{lead.job_id || "-"}</strong>
        </div>
        <div>
          <span className="label">Created</span>
          <strong>{lead.created_at || "-"}</strong>
        </div>
        <div>
          <span className="label">Updated</span>
          <strong>{lead.updated_at || "-"}</strong>
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
        <button type="submit" disabled={updateLead.isPending || !lead.lead_id}>
          {updateLead.isPending ? <Loader2 className="spin" size={17} /> : <CheckCircle2 size={17} />}
          Save lead
        </button>
        <ErrorAlert error={updateLead.error} />
      </form>
    </section>
  );
}

function LeadsPage() {
  const [status, setStatus] = useState("");
  const [jobId, setJobId] = useState("");
  const [hasEmail, setHasEmail] = useState("");
  const [hasWebsite, setHasWebsite] = useState("");
  const [selectedLead, setSelectedLead] = useState<Lead>();
  const leads = useLeads({
    status: status || undefined,
    job_id: jobId || undefined,
    has_email: hasEmail === "" ? undefined : hasEmail === "true",
    has_website: hasWebsite === "" ? undefined : hasWebsite === "true",
  });

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
        <button
          className="secondary"
          type="button"
          onClick={() => {
            setStatus("");
            setHasWebsite("true");
            setHasEmail("false");
          }}
        >
          Needs enrichment
        </button>
      </section>
      <section className="grid leads-layout">
        <section className="panel">
          <div className="section-head">
            <div>
              <h2>Stored leads</h2>
              <p>{leads.data?.count ?? 0} matching records</p>
            </div>
            <button className="secondary" type="button" onClick={() => void downloadExportedLeads()}>
              <Download size={17} />
              Export CSV
            </button>
          </div>
          {leads.isLoading ? (
            <div className="muted">Loading leads...</div>
          ) : leads.isError ? (
            <ErrorAlert error={leads.error} />
          ) : (
            <LeadsTable
              leads={leads.data?.leads ?? []}
              selectedLeadId={selectedLead?.lead_id}
              onSelectLead={setSelectedLead}
              showActions
            />
          )}
        </section>
        <LeadDetailPanel lead={selectedLead} onLeadUpdated={setSelectedLead} />
      </section>
    </>
  );
}

function SettingsPage() {
  return (
    <>
      <PageHeader
        title="Settings"
        description="Frontend runtime defaults. Backend operational settings are environment-driven today."
      />
      <section className="panel settings-grid">
        <div>
          <span className="label">API base</span>
          <strong>/api</strong>
        </div>
        <div>
          <span className="label">Health proxy</span>
          <strong>/backend-health</strong>
        </div>
        <div>
          <span className="label">Polling interval</span>
          <strong>3 seconds</strong>
        </div>
      </section>
    </>
  );
}

function CurrentPage({ page }: { page: PageId }) {
  if (page === "discover") return <DiscoverPage />;
  if (page === "website") return <WebsiteEmailPage />;
  if (page === "enrich") return <EnrichPage />;
  if (page === "leads") return <LeadsPage />;
  if (page === "jobs") return <JobsPage />;
  if (page === "settings") return <SettingsPage />;
  return <DashboardPage />;
}

export function App() {
  const [page, setPage] = useState<PageId>("dashboard");
  const health = useBackendHealth();
  const queryClient = useQueryClient();

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">SC</div>
          <div>
            <strong>Scraping Console</strong>
            <span>Lead operations</span>
          </div>
        </div>
        <nav>
          {pages.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.id}
                type="button"
                className={page === item.id ? "active" : ""}
                onClick={() => setPage(item.id)}
              >
                <Icon size={18} />
                {item.label}
              </button>
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
        <CurrentPage page={page} />
      </main>
    </div>
  );
}
