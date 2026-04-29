import { useMemo, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import {
  Activity,
  Building2,
  CheckCircle2,
  Download,
  Globe2,
  Loader2,
  Mail,
  Play,
  Search,
  Settings,
  Square,
  Table2,
} from "lucide-react";
import { ApiError, type Lead } from "./api";
import {
  useBackendHealth,
  useExportLeadsJson,
  useGoogleMapsScrape,
  useJobPolling,
  useLeadEmailEnrichment,
  useStopJob,
  useWebsiteEmailScrape,
} from "./hooks";
import { downloadExportedLeads } from "./hooks";

type PageId = "dashboard" | "discover" | "website" | "enrich" | "leads" | "settings";

const pages: Array<{ id: PageId; label: string; icon: typeof Activity }> = [
  { id: "dashboard", label: "Dashboard", icon: Activity },
  { id: "discover", label: "Find Businesses", icon: Building2 },
  { id: "website", label: "Website Emails", icon: Globe2 },
  { id: "enrich", label: "Enrich Leads", icon: Mail },
  { id: "leads", label: "Leads", icon: Table2 },
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

function LeadsTable({ leads }: { leads: Lead[] }) {
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
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Location</th>
            <th>Phone</th>
            <th>Website</th>
            <th>Emails</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {leads.map((lead, index) => (
            <tr key={`${lead.place_id ?? lead.lead_id ?? index}-${index}`}>
              <td>{lead.name || "Untitled"}</td>
              <td>{lead.location || lead.address || "-"}</td>
              <td>{lead.phone || "-"}</td>
              <td>
                {lead.website ? (
                  <a href={lead.website} target="_blank" rel="noreferrer">
                    {lead.website}
                  </a>
                ) : (
                  "-"
                )}
              </td>
              <td>{lead.emails || "-"}</td>
              <td>{lead.status ? <StatusBadge status={lead.status} /> : "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function DashboardPage() {
  const health = useBackendHealth();

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

function LeadsPage() {
  const leads = useExportLeadsJson();
  const exportLeads = leads.data && "leads" in leads.data ? leads.data.leads : [];

  return (
    <>
      <PageHeader
        title="Leads"
        description="Review export-ready leads. The backend currently exposes only scraped leads with phone or email."
      />
      <section className="panel">
        <div className="section-head">
          <div>
            <h2>Export-ready leads</h2>
            <p>{leads.data?.count ?? 0} contacts available</p>
          </div>
          <button className="secondary" type="button" onClick={() => void downloadExportedLeads()}>
            <Download size={17} />
            CSV
          </button>
        </div>
        {leads.isLoading ? (
          <div className="muted">Loading leads...</div>
        ) : leads.isError ? (
          <ErrorAlert error={leads.error} />
        ) : (
          <LeadsTable leads={exportLeads} />
        )}
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
  if (page === "settings") return <SettingsPage />;
  return <DashboardPage />;
}

export function App() {
  const [page, setPage] = useState<PageId>("dashboard");
  const health = useBackendHealth();

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
          {health.isSuccess ? <StatusBadge status={health.data.status} /> : <StatusBadge />}
        </div>
        <CurrentPage page={page} />
      </main>
    </div>
  );
}
