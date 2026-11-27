import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  BadgePoundSterling,
  CalendarDays,
  Check,
  ChevronDown,
  CircleAlert,
  CircleCheckBig,
  CircleX,
  Clock3,
  ExternalLink,
  FileCheck2,
  FilePlus2,
  Files,
  GitCompareArrows,
  Link2,
  LoaderCircle,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  Pencil,
  Plus,
  RefreshCw,
  Radar,
  Search,
  Trash2,
  UserRound,
  UsersRound,
  X,
} from "lucide-react";


const API_BASE = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");

const emptyCreateForm = {
  learnerId: "",
  fullName: "",
  email: "",
  programName: "",
  category: "CONTRACT",
  documentName: "",
  file: "",
  status: "Added manually",
  updatedTo: "",
};

function apiUrl(path) {
  return `${API_BASE}${path}`;
}

function pageFromHash() {
  if (window.location.hash === "#date-comparison") return "comparison";
  if (window.location.hash === "#hours-comparison") return "hours-comparison";
  if (window.location.hash === "#monthly-hours") return "monthly-hours";
  if (window.location.hash === "#skills-radar") return "skills-radar";
  if (window.location.hash === "#funding-comparison") return "funding-comparison";
  if (window.location.hash === "#prior-learning") return "prior-learning";
  if (window.location.hash === "#endpoint-assessment") return "endpoint-assessment";
  return "documents";
}

function formatNumber(value) {
  return new Intl.NumberFormat("en-GB").format(Number(value) || 0);
}

function formatDate(value) {
  if (!value) return "No date";
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(value));
}

function formatHours(value) {
  if (value === null || value === undefined || value === "") return "Missing";
  return new Intl.NumberFormat("en-GB", { maximumFractionDigits: 2 }).format(Number(value));
}

function formatCurrency(value) {
  if (value === null || value === undefined || value === "") return "—";
  return new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency: "GBP",
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(Number(value));
}

function toDateInput(value) {
  if (!value) return "";
  return String(value).slice(0, 10);
}

function statusTone(status = "") {
  const normalized = String(status || "").toLowerCase();
  if (normalized.includes("verified") || normalized.includes("signed")) return "success";
  if (normalized.includes("pending") || normalized.includes("requested")) return "warning";
  return "neutral";
}

function programStatusTone(status = "") {
  const normalized = String(status || "").toLowerCase();
  if (normalized === "active") return "active";
  if (normalized.includes("withdraw")) return "withdrawn";
  if (normalized.includes("onboarding") || normalized.includes("enrol") || normalized.includes("review")) return "pending";
  return "unknown";
}

function ProgramStatusBadge({ status }) {
  return (
    <span className={`program-status-badge ${programStatusTone(status)}`}>
      <i /> {status || "Not available"}
    </span>
  );
}

async function getResponseMessage(response, fallback) {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.message || fallback);
  return data;
}

function SummaryCard({ icon: Icon, label, value, tone, detail, onClick, active = false }) {
  const content = (
    <>
      <div className={`summary-icon ${tone}`}>
        <Icon size={21} strokeWidth={1.9} />
      </div>
      <div>
        <span className="summary-label">{label}</span>
        <strong className="summary-value">{formatNumber(value)}</strong>
        <span className="summary-detail">{detail}</span>
      </div>
    </>
  );

  if (onClick) {
    return (
      <button
        type="button"
        className={`summary-card is-clickable ${active ? "is-active" : ""}`}
        onClick={onClick}
        aria-pressed={active}
      >
        {content}
      </button>
    );
  }

  return <article className="summary-card">{content}</article>;
}

function ProgramStatusFilter({ value, statuses = [], onChange }) {
  const [open, setOpen] = useState(false);
  const filterRef = useRef(null);
  const options = [
    { value: "all", label: "All statuses" },
    ...statuses.map((status) => ({ value: status.toLowerCase(), label: status })),
  ];
  const selected = options.find((option) => option.value === value) ?? options[0];

  useEffect(() => {
    function closeMenu(event) {
      if (filterRef.current && !filterRef.current.contains(event.target)) {
        setOpen(false);
      }
    }

    function closeOnEscape(event) {
      if (event.key === "Escape") setOpen(false);
    }

    document.addEventListener("mousedown", closeMenu);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("mousedown", closeMenu);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, []);

  function selectStatus(status) {
    onChange(status);
    setOpen(false);
  }

  return (
    <div className={`program-status-filter ${open ? "is-open" : ""}`} ref={filterRef}>
      <button
        type="button"
        className="program-status-trigger"
        onClick={() => setOpen((current) => !current)}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <span>Program status</span>
        <strong>{selected.label}</strong>
        <ChevronDown size={15} />
      </button>
      {open && (
        <div className="program-status-menu" role="listbox" aria-label="Filter by program status">
          {options.map((option) => (
            <button
              type="button"
              role="option"
              key={option.value}
              aria-selected={option.value === value}
              className={option.value === value ? "active" : ""}
              onClick={() => selectStatus(option.value)}
            >
              <span className={`status-option-dot ${option.value === "all" ? "all" : programStatusTone(option.label)}`} />
              <strong>{option.label}</strong>
              {option.value === value && <Check size={15} />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function YearFilter({ value, years = [], onChange }) {
  const [open, setOpen] = useState(false);
  const filterRef = useRef(null);

  useEffect(() => {
    function closeMenu(event) {
      if (filterRef.current && !filterRef.current.contains(event.target)) {
        setOpen(false);
      }
    }

    function closeOnEscape(event) {
      if (event.key === "Escape") setOpen(false);
    }

    document.addEventListener("mousedown", closeMenu);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("mousedown", closeMenu);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, []);

  function selectYear(nextYear) {
    onChange(String(nextYear));
    setOpen(false);
  }

  return (
    <div className={`monthly-year-filter ${open ? "is-open" : ""}`} ref={filterRef}>
      <button
        type="button"
        className="monthly-year-trigger"
        onClick={() => setOpen((current) => !current)}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <CalendarDays size={16} />
        <span>Year</span>
        <strong>{value}</strong>
        <ChevronDown size={15} />
      </button>
      {open && (
        <div className="monthly-year-menu" role="listbox" aria-label="Select hours year">
          {years.map((availableYear) => {
            const optionValue = String(availableYear);
            const selected = optionValue === value;
            return (
              <button
                type="button"
                role="option"
                key={optionValue}
                aria-selected={selected}
                className={selected ? "active" : ""}
                onClick={() => selectYear(optionValue)}
              >
                <CalendarDays size={14} />
                <strong>{optionValue}</strong>
                {selected && <Check size={15} />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

function RefetchWrittenAgreementsButton({ scope, onComplete }) {
  const [job, setJob] = useState(null);
  const [error, setError] = useState("");
  const running = job?.status === "queued" || job?.status === "running";

  useEffect(() => {
    if (!running || !job?.id) return undefined;
    const timeout = setTimeout(async () => {
      try {
        const response = await fetch(apiUrl(`/api/written-agreement-refetch/${job.id}/`), {
          cache: "no-store",
        });
        const nextJob = await getResponseMessage(response, "Unable to load refetch progress.");
        setJob(nextJob);
        if (nextJob.status === "completed") onComplete?.();
        if (nextJob.status === "failed") setError(nextJob.message || "Refetch failed.");
      } catch (pollError) {
        setError(pollError.message);
        setJob((current) => (current ? { ...current } : current));
      }
    }, 1400);
    return () => clearTimeout(timeout);
  }, [job, onComplete, running]);

  async function startRefetch() {
    setError("");
    try {
      const response = await fetch(apiUrl("/api/written-agreement-refetch/"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scope }),
      });
      const nextJob = await getResponseMessage(response, "Unable to start refetch.");
      setJob(nextJob);
    } catch (startError) {
      setError(startError.message);
    }
  }

  const progress = job?.total
    ? `${formatNumber(job.processed)}/${formatNumber(job.total)}`
    : "Starting...";

  return (
    <div className="refetch-control">
      <button className="refetch-button" type="button" onClick={startRefetch} disabled={running}>
        <RefreshCw size={16} className={running ? "spin" : ""} />
        {running ? `Refetching ${progress}` : "Refetch agreements"}
      </button>
      {!running && job?.status === "completed" && (
        <small>{formatNumber(job.extracted)} extracted · {formatNumber(job.updated_links)} links updated</small>
      )}
      {error && <small className="error">{error}</small>}
    </div>
  );
}

function Modal({ title, subtitle, children, onClose, wide = false }) {
  useEffect(() => {
    const closeOnEscape = (event) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [onClose]);

  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <section
        className={`modal ${wide ? "modal-wide" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="modal-head">
          <div>
            <h2>{title}</h2>
            {subtitle && <p>{subtitle}</p>}
          </div>
          <button className="icon-button" onClick={onClose} aria-label="Close">
            <X size={19} />
          </button>
        </div>
        {children}
      </section>
    </div>
  );
}

function Field({ label, required, children, className = "" }) {
  return (
    <label className={`field ${className}`}>
      <span>
        {label} {required && <b>*</b>}
      </span>
      {children}
    </label>
  );
}

function DocumentCell({ documents, onEdit }) {
  if (!documents?.length) {
    return <span className="empty-document">—</span>;
  }

  return (
    <div className="document-stack">
      {documents.map((document) => (
        <div className="document-chip" key={document.id} title={document.document_name}>
          <span className={`document-status-dot ${statusTone(document.status)}`} />
          <div className="document-chip-copy">
            <strong>{document.status || "Not set"}</strong>
            <small>{document.document_name}</small>
          </div>
          {document.file && (
            <a
              href={document.file}
              target="_blank"
              rel="noreferrer"
              aria-label={`Open ${document.document_name}`}
              title="Open document"
            >
              <ExternalLink size={14} />
            </a>
          )}
          <button
            type="button"
            onClick={() => onEdit(document)}
            aria-label={`Edit ${document.document_name}`}
            title="Edit document"
          >
            <Pencil size={14} />
          </button>
        </div>
      ))}
    </div>
  );
}

function UpdatedToCell({ documents, onEdit }) {
  if (!documents?.length) {
    return <span className="empty-document">—</span>;
  }

  return (
    <div className="updated-to-stack">
      {documents.map((document) => (
        <button
          type="button"
          className={`updated-to-button ${document.updated_to ? "has-date" : ""}`}
          key={document.id}
          onClick={() => onEdit(document)}
          title={`Edit date for ${document.document_name}`}
        >
          <CalendarDays size={14} />
          <span>
            <strong>{document.updated_to ? formatDate(document.updated_to) : "Set date"}</strong>
            <small>Updated to</small>
          </span>
        </button>
      ))}
    </div>
  );
}

function DateComparisonPage() {
  const [data, setData] = useState(null);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [editingAgreement, setEditingAgreement] = useState(null);
  const [agreementDate, setAgreementDate] = useState("");
  const [savingAgreement, setSavingAgreement] = useState(false);
  const [feedback, setFeedback] = useState(null);
  const [comparisonFilter, setComparisonFilter] = useState("all");
  const [programStatus, setProgramStatus] = useState("all");

  const summary = data?.summary ?? {};
  const pagination = data?.pagination ?? { page: 1, pages: 1, total: 0 };

  const queryString = useMemo(() => {
    const params = new URLSearchParams({ page: String(page) });
    params.set("filter", comparisonFilter);
    params.set("programStatus", programStatus);
    if (search.trim()) params.set("search", search.trim());
    return params.toString();
  }, [page, search, comparisonFilter, programStatus]);

  async function loadComparisons({ quiet = false } = {}) {
    if (!quiet) setLoading(true);
    setError("");
    try {
      const response = await fetch(apiUrl(`/api/start-date-comparisons/?${queryString}`), {
        cache: "no-store",
      });
      const nextData = await getResponseMessage(response, "Unable to load comparison data.");
      setData(nextData);
    } catch (loadError) {
      setError(loadError.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const timeout = setTimeout(() => loadComparisons(), search ? 350 : 0);
    return () => clearTimeout(timeout);
    // queryString contains the complete comparison filter state.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queryString]);

  function changeSearch(value) {
    setPage(1);
    setSearch(value);
  }

  function changeComparisonFilter(value) {
    setPage(1);
    setComparisonFilter(value);
  }

  function changeProgramStatus(value) {
    setPage(1);
    setProgramStatus(value);
  }

  function openAgreementEditor(learner) {
    setEditingAgreement(learner);
    setAgreementDate(toDateInput(learner.apprenticeship_agreement_date));
  }

  async function saveAgreementDate(event) {
    event.preventDefault();
    setSavingAgreement(true);
    try {
      const response = await fetch(apiUrl(
        `/api/start-date-comparisons/apprenticeship-agreement/${editingAgreement.apprenticeship_agreement_document_id}/`
      ), {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ apprenticeshipAgreementDate: agreementDate }),
      });
      const result = await getResponseMessage(response, "Unable to update Apprenticeship Agreement date.");
      setEditingAgreement(null);
      setFeedback({ tone: "success", message: result.message });
      await loadComparisons({ quiet: true });
    } catch (saveError) {
      setFeedback({ tone: "error", message: saveError.message });
    } finally {
      setSavingAgreement(false);
    }
  }

  useEffect(() => {
    if (!feedback) return;
    const timeout = setTimeout(() => setFeedback(null), 3200);
    return () => clearTimeout(timeout);
  }, [feedback]);

  return (
    <div className="page comparison-page">
      <section className="hero">
        <div>
          <span className="eyebrow">DATE AUDIT</span>
          <h1>Start Date Comparison</h1>
          <p>Compare the ILR start date with the Apprenticeship Agreement and first submitted evidence.</p>
        </div>
      </section>

      <section className="summary-grid comparison-summary-grid">
        <SummaryCard icon={UsersRound} label="ILR learners" value={summary.learners} detail="Learners reviewed" tone="blue" onClick={() => changeComparisonFilter("all")} active={comparisonFilter === "all"} />
        <SummaryCard icon={CircleCheckBig} label="Matched" value={summary.matched} detail="Apprenticeship Agreement on/before start" tone="green" onClick={() => changeComparisonFilter("matched")} active={comparisonFilter === "matched"} />
        <SummaryCard icon={CircleX} label="Not matched" value={summary.notMatched} detail="Apprenticeship Agreement after start" tone="orange" onClick={() => changeComparisonFilter("not-matched")} active={comparisonFilter === "not-matched"} />
        <SummaryCard icon={CircleAlert} label="Missing dates" value={summary.missingDates} detail="One or more dates missing" tone="purple" onClick={() => changeComparisonFilter("missing")} active={comparisonFilter === "missing"} />
      </section>

      <section className="date-pair-summary-grid">
        <SummaryCard icon={CalendarDays} label="Start & evidence matched" value={summary.evidenceMatched} detail="First evidence is on the start date" tone="green" onClick={() => changeComparisonFilter("evidence-matched")} active={comparisonFilter === "evidence-matched"} />
        <SummaryCard icon={CircleX} label="Start & evidence mismatched" value={summary.evidenceMismatched} detail="First evidence is after the start date" tone="orange" onClick={() => changeComparisonFilter("evidence-mismatched")} active={comparisonFilter === "evidence-mismatched"} />
      </section>

      <section className="content-card comparison-card">
        <div className="content-heading">
          <div>
            <h2>Learner date comparison</h2>
            <p>{formatNumber(pagination.total)} learners · one learner per row</p>
          </div>
          <button className="refresh-button" onClick={() => loadComparisons()} disabled={loading}>
            <RefreshCw size={16} className={loading ? "spin" : ""} /> Refresh
          </button>
        </div>

        <div className="comparison-toolbar">
          <label className="search-box">
            <Search size={18} />
            <input
              value={search}
              onChange={(event) => changeSearch(event.target.value)}
              placeholder="Search by learner, email or programme..."
            />
            {search && (
              <button type="button" onClick={() => changeSearch("")} aria-label="Clear search">
                <X size={16} />
              </button>
            )}
          </label>
          <ProgramStatusFilter value={programStatus} statuses={data?.programStatuses} onChange={changeProgramStatus} />
        </div>

        {error ? (
          <div className="state-panel error-state">
            <CircleAlert size={26} />
            <div><strong>Could not load the comparison</strong><p>{error}</p></div>
            <button onClick={() => loadComparisons()}>Try again</button>
          </div>
        ) : (
          <div className={`table-wrap comparison-table-wrap ${loading ? "is-loading" : ""}`}>
            {loading && <div className="loading-layer"><LoaderCircle size={26} className="spin" /></div>}
            <table className="comparison-table">
              <thead>
                <tr>
                  <th>Learner</th>
                  <th>Programme</th>
                  <th>Program status</th>
                  <th>ILR start date</th>
                  <th>First evidence</th>
                  <th>Apprenticeship Agreement</th>
                  <th>Comparison</th>
                </tr>
              </thead>
              <tbody>
                {data?.rows?.map((learner) => (
                  <tr key={learner.learn_ref_number}>
                    <td>
                      <div className="person-cell comparison-person">
                        <span className="avatar">{learner.full_name?.trim()?.[0]?.toUpperCase() || "?"}</span>
                        <div>
                          <strong>{learner.full_name}</strong>
                          <small>{learner.email}</small>
                        </div>
                      </div>
                    </td>
                    <td><span className="comparison-programme">{learner.program_name || "—"}</span></td>
                    <td><ProgramStatusBadge status={learner.program_status} /></td>
                    <td><span className="comparison-date primary-date">{learner.learn_start_date ? formatDate(learner.learn_start_date) : "—"}</span></td>
                    <td>
                      <div className="evidence-date-cell">
                        <span className="comparison-date">{learner.first_evidence_date ? formatDate(learner.first_evidence_date) : "Missing"}</span>
                        {learner.first_evidence_name && <small>{learner.first_evidence_name}</small>}
                      </div>
                    </td>
                    <td>
                      <div className="agreement-date-cell">
                        <span className="comparison-date">{learner.apprenticeship_agreement_date ? formatDate(learner.apprenticeship_agreement_date) : "Missing"}</span>
                        {learner.apprenticeship_agreement_date_is_manual && <small>Manual override</small>}
                        {learner.apprenticeship_agreement_date_is_pre_start_version && <small>On/before start version</small>}
                        {learner.apprenticeship_agreement_date_is_after_start_version && <small>Closest after start</small>}
                        {learner.apprenticeship_agreement_document_id && (
                          <button
                            type="button"
                            onClick={() => openAgreementEditor(learner)}
                            aria-label={`Edit Apprenticeship Agreement date for ${learner.full_name}`}
                            title="Edit Apprenticeship Agreement date"
                          >
                            <Pencil size={14} /> Edit
                          </button>
                        )}
                      </div>
                    </td>
                    <td>
                      <div className={`comparison-result ${learner.is_matched ? "matched" : "not-matched"}`}>
                        {learner.is_matched ? <CircleCheckBig size={16} /> : <CircleX size={16} />}
                        <span><strong>{learner.is_matched ? "Matched" : "Not matched"}</strong><small>{learner.match_reason}</small></span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!loading && !data?.rows?.length && (
              <div className="empty-state">
                <div><Search size={25} /></div>
                <strong>No learners found</strong>
                <p>Try a different search term.</p>
              </div>
            )}
          </div>
        )}

        {!error && (
          <div className="pagination">
            <span>Page <b>{pagination.page}</b> of <b>{pagination.pages}</b></span>
            <div>
              <button onClick={() => setPage((current) => Math.max(current - 1, 1))} disabled={page <= 1 || loading}>
                <ArrowLeft size={17} /> Previous
              </button>
              <button onClick={() => setPage((current) => Math.min(current + 1, pagination.pages))} disabled={page >= pagination.pages || loading}>
                Next <ArrowRight size={17} />
              </button>
            </div>
          </div>
        )}
      </section>

      {editingAgreement && (
        <Modal
          title="Edit Apprenticeship Agreement date"
          subtitle={`${editingAgreement.full_name} · ${editingAgreement.program_name || "ILR learner"}`}
          onClose={() => !savingAgreement && setEditingAgreement(null)}
        >
          <form onSubmit={saveAgreementDate}>
            <div className="modal-body">
              <div className="learner-summary">
                <span><CalendarDays size={18} /></span>
                <div>
                  <strong>ILR start date: {formatDate(editingAgreement.learn_start_date)}</strong>
                  <small>The comparison updates automatically after saving.</small>
                </div>
              </div>
              <Field label="Apprenticeship Agreement date" required>
                <div className="date-input">
                  <CalendarDays size={17} />
                  <input
                    type="date"
                    value={agreementDate}
                    onChange={(event) => setAgreementDate(event.target.value)}
                    required
                  />
                </div>
              </Field>
            </div>
            <div className="modal-actions">
              <button type="button" className="secondary-button" onClick={() => setEditingAgreement(null)} disabled={savingAgreement}>Cancel</button>
              <button type="submit" className="primary-button" disabled={savingAgreement}>
                {savingAgreement ? <LoaderCircle size={17} className="spin" /> : <Check size={17} />} Save date
              </button>
            </div>
          </form>
        </Modal>
      )}

      {feedback && (
        <div className={`toast ${feedback.tone}`} role="status">
          {feedback.tone === "success" ? <Check size={18} /> : <CircleAlert size={18} />}
          <span>{feedback.message}</span>
          <button onClick={() => setFeedback(null)} aria-label="Dismiss"><X size={16} /></button>
        </div>
      )}
    </div>
  );
}

function PlannedHoursComparisonPage() {
  const [data, setData] = useState(null);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [comparisonFilter, setComparisonFilter] = useState("all");
  const [programStatus, setProgramStatus] = useState("all");

  const summary = data?.summary ?? {};
  const pagination = data?.pagination ?? { page: 1, pages: 1, total: 0 };

  const queryString = useMemo(() => {
    const params = new URLSearchParams({
      page: String(page),
      filter: comparisonFilter,
      programStatus,
    });
    if (search.trim()) params.set("search", search.trim());
    return params.toString();
  }, [page, search, comparisonFilter, programStatus]);

  async function loadComparisons() {
    setLoading(true);
    setError("");
    try {
      const response = await fetch(apiUrl(`/api/planned-hours-comparisons/?${queryString}`), {
        cache: "no-store",
      });
      const nextData = await getResponseMessage(response, "Unable to load hours comparison data.");
      setData(nextData);
    } catch (loadError) {
      setError(loadError.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const timeout = setTimeout(() => loadComparisons(), search ? 350 : 0);
    return () => clearTimeout(timeout);
    // queryString contains the complete comparison filter state.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queryString]);

  function changeFilter(value) {
    setPage(1);
    setComparisonFilter(value);
  }

  function changeSearch(value) {
    setPage(1);
    setSearch(value);
  }

  function changeProgramStatus(value) {
    setPage(1);
    setProgramStatus(value);
  }

  return (
    <div className="page comparison-page">
      <section className="hero">
        <div>
          <span className="eyebrow">HOURS AUDIT</span>
          <h1>Planned Hours Comparison</h1>
          <p>Compare planned hours across the ILR, Training Plan and Apprenticeship Agreement.</p>
        </div>
      </section>

      <section className="summary-grid comparison-summary-grid">
        <SummaryCard icon={UsersRound} label="ILR learners" value={summary.learners} detail="Learners reviewed" tone="blue" onClick={() => changeFilter("all")} active={comparisonFilter === "all"} />
        <SummaryCard icon={CircleCheckBig} label="Matched" value={summary.matched} detail="All three values match" tone="green" onClick={() => changeFilter("matched")} active={comparisonFilter === "matched"} />
        <SummaryCard icon={CircleX} label="Mismatched" value={summary.mismatched} detail="Values are different" tone="orange" onClick={() => changeFilter("mismatched")} active={comparisonFilter === "mismatched"} />
        <SummaryCard icon={CircleAlert} label="Missing values" value={summary.missingValues} detail="One or more values missing" tone="purple" onClick={() => changeFilter("missing")} active={comparisonFilter === "missing"} />
      </section>

      <section className="content-card comparison-card">
        <div className="content-heading">
          <div>
            <h2>Learner planned-hours comparison</h2>
            <p>{formatNumber(pagination.total)} learners · one learner per row</p>
          </div>
          <button className="refresh-button" onClick={() => loadComparisons()} disabled={loading}>
            <RefreshCw size={16} className={loading ? "spin" : ""} /> Refresh
          </button>
        </div>

        <div className="comparison-toolbar">
          <label className="search-box">
            <Search size={18} />
            <input
              value={search}
              onChange={(event) => changeSearch(event.target.value)}
              placeholder="Search by learner, email or programme..."
            />
            {search && (
              <button type="button" onClick={() => changeSearch("")} aria-label="Clear search">
                <X size={16} />
              </button>
            )}
          </label>
          <ProgramStatusFilter value={programStatus} statuses={data?.programStatuses} onChange={changeProgramStatus} />
        </div>

        {error ? (
          <div className="state-panel error-state">
            <CircleAlert size={26} />
            <div><strong>Could not load the comparison</strong><p>{error}</p></div>
            <button onClick={() => loadComparisons()}>Try again</button>
          </div>
        ) : (
          <div className={`table-wrap comparison-table-wrap ${loading ? "is-loading" : ""}`}>
            {loading && <div className="loading-layer"><LoaderCircle size={26} className="spin" /></div>}
            <table className="comparison-table hours-comparison-table">
              <thead>
                <tr>
                  <th>Learner</th>
                  <th>Programme</th>
                  <th>Program status</th>
                  <th>ILR planned hours</th>
                  <th>Training Plan hours</th>
                  <th>Agreement hours</th>
                  <th>Comparison</th>
                </tr>
              </thead>
              <tbody>
                {data?.rows?.map((learner) => (
                  <tr key={learner.learn_ref_number}>
                    <td>
                      <div className="person-cell comparison-person">
                        <span className="avatar">{learner.full_name?.trim()?.[0]?.toUpperCase() || "?"}</span>
                        <div><strong>{learner.full_name}</strong><small>{learner.email}</small></div>
                      </div>
                    </td>
                    <td><span className="comparison-programme">{learner.program_name || "—"}</span></td>
                    <td><ProgramStatusBadge status={learner.program_status} /></td>
                    <td><span className={`hours-value ${learner.ilr_planned_hours == null ? "is-missing" : ""}`}>{formatHours(learner.ilr_planned_hours)}</span></td>
                    <td><span className={`hours-value ${learner.training_plan_planned_hours == null ? "is-missing" : ""}`}>{formatHours(learner.training_plan_planned_hours)}</span></td>
                    <td><span className={`hours-value ${learner.apprenticeship_agreement_planned_hours == null ? "is-missing" : ""}`}>{formatHours(learner.apprenticeship_agreement_planned_hours)}</span></td>
                    <td>
                      <div className={`comparison-result ${learner.comparison_status === "matched" ? "matched" : learner.comparison_status === "missing" ? "missing" : "not-matched"}`}>
                        {learner.comparison_status === "matched" ? <CircleCheckBig size={16} /> : learner.comparison_status === "missing" ? <CircleAlert size={16} /> : <CircleX size={16} />}
                        <span>
                          <strong>{learner.comparison_status === "matched" ? "Matched" : learner.comparison_status === "missing" ? "Missing" : "Mismatched"}</strong>
                          <small>{learner.comparison_reason}</small>
                        </span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!loading && !data?.rows?.length && (
              <div className="empty-state">
                <div><Search size={25} /></div>
                <strong>No learners found</strong>
                <p>Try a different search term or comparison filter.</p>
              </div>
            )}
          </div>
        )}

        {!error && (
          <div className="pagination">
            <span>Page <b>{pagination.page}</b> of <b>{pagination.pages}</b></span>
            <div>
              <button onClick={() => setPage((current) => Math.max(current - 1, 1))} disabled={page <= 1 || loading}>
                <ArrowLeft size={17} /> Previous
              </button>
              <button onClick={() => setPage((current) => Math.min(current + 1, pagination.pages))} disabled={page >= pagination.pages || loading}>
                Next <ArrowRight size={17} />
              </button>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

function FundingComparisonPage() {
  const [data, setData] = useState(null);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [comparisonFilter, setComparisonFilter] = useState("all");
  const [programStatus, setProgramStatus] = useState("all");

  const summary = data?.summary ?? {};
  const itemColumns = data?.itemColumns ?? [];
  const referenceColumns = data?.referenceColumns ?? [];
  const ilrColumns = data?.ilrColumns ?? [];
  const pagination = data?.pagination ?? { page: 1, pages: 1, total: 0 };

  const queryString = useMemo(() => {
    const params = new URLSearchParams({
      page: String(page),
      filter: comparisonFilter,
      programStatus,
    });
    if (search.trim()) params.set("search", search.trim());
    return params.toString();
  }, [page, search, comparisonFilter, programStatus]);

  async function loadComparisons() {
    setLoading(true);
    setError("");
    try {
      const response = await fetch(apiUrl(`/api/funding-comparisons/?${queryString}`), {
        cache: "no-store",
      });
      const nextData = await getResponseMessage(response, "Unable to load funding comparison data.");
      setData(nextData);
    } catch (loadError) {
      setError(loadError.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const timeout = setTimeout(() => loadComparisons(), search ? 350 : 0);
    return () => clearTimeout(timeout);
    // queryString contains the complete comparison filter state.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queryString]);

  function changeFilter(value) {
    setPage(1);
    setComparisonFilter(value);
  }

  function changeSearch(value) {
    setPage(1);
    setSearch(value);
  }

  function changeProgramStatus(value) {
    setPage(1);
    setProgramStatus(value);
  }

  return (
    <div className="page comparison-page funding-page">
      <section className="hero">
        <div>
          <span className="eyebrow">FUNDING AUDIT</span>
          <h1>Written Agreement Funding</h1>
          <p>Validate the Written Agreement calculation, then compare its total with the latest ILR TNP funding.</p>
        </div>
      </section>

      <section className="summary-grid comparison-summary-grid funding-summary-grid">
        <SummaryCard icon={UsersRound} label="ILR learners" value={summary.learners} detail="Latest programme per learner" tone="blue" onClick={() => changeFilter("all")} active={comparisonFilter === "all"} />
        <SummaryCard icon={CircleCheckBig} label="Agreement correct" value={summary.agreementMatched} detail="Cost items equal the JSON total" tone="green" onClick={() => changeFilter("agreement-matched")} active={comparisonFilter === "agreement-matched"} />
        <SummaryCard icon={CircleX} label="Agreement incorrect" value={summary.agreementMismatched} detail="Cost items and JSON total differ" tone="orange" onClick={() => changeFilter("agreement-mismatched")} active={comparisonFilter === "agreement-mismatched"} />
        <SummaryCard icon={CircleCheckBig} label="ILR & Agreement matched" value={summary.totalsMatched} detail="ILR total equals Agreement total" tone="green" onClick={() => changeFilter("totals-matched")} active={comparisonFilter === "totals-matched"} />
        <SummaryCard icon={CircleX} label="ILR & Agreement mismatched" value={summary.totalsMismatched} detail="ILR and Agreement totals differ" tone="orange" onClick={() => changeFilter("totals-mismatched")} active={comparisonFilter === "totals-mismatched"} />
        <SummaryCard icon={CircleAlert} label="Missing data" value={summary.missingValues} detail="One or both checks are incomplete" tone="purple" onClick={() => changeFilter("missing")} active={comparisonFilter === "missing"} />
      </section>

      <section className="content-card comparison-card funding-card">
        <div className="content-heading">
          <div>
            <h2>Funding validation checks</h2>
            <p>{formatNumber(pagination.total)} learners · one learner per row</p>
          </div>
          <div className="content-actions">
            <RefetchWrittenAgreementsButton scope="funding" onComplete={loadComparisons} />
            <button className="refresh-button" onClick={() => loadComparisons()} disabled={loading}>
              <RefreshCw size={16} className={loading ? "spin" : ""} /> Refresh
            </button>
          </div>
        </div>

        <div className="comparison-toolbar">
          <label className="search-box">
            <Search size={18} />
            <input
              value={search}
              onChange={(event) => changeSearch(event.target.value)}
              placeholder="Search by learner, email, programme or document ID..."
            />
            {search && (
              <button type="button" onClick={() => changeSearch("")} aria-label="Clear search">
                <X size={16} />
              </button>
            )}
          </label>
          <ProgramStatusFilter value={programStatus} statuses={data?.programStatuses} onChange={changeProgramStatus} />
        </div>

        {error ? (
          <div className="state-panel error-state">
            <CircleAlert size={26} />
            <div><strong>Could not load the funding comparison</strong><p>{error}</p></div>
            <button onClick={() => loadComparisons()}>Try again</button>
          </div>
        ) : (
          <div className={`table-wrap comparison-table-wrap funding-table-wrap ${loading ? "is-loading" : ""}`}>
            {loading && <div className="loading-layer"><LoaderCircle size={26} className="spin" /></div>}
            <table className="comparison-table funding-comparison-table">
              <thead>
                <tr className="funding-group-row">
                  <th className="sticky-learner" rowSpan="2">Learner</th>
                  <th className="sticky-programme" rowSpan="2">Programme</th>
                  <th className="sticky-status" rowSpan="2">Program status</th>
                  <th className="sticky-agreement" rowSpan="2">Agreement</th>
                  {ilrColumns.length > 0 && <th colSpan={ilrColumns.length + 2}>Latest ILR TNP · PMR excluded</th>}
                  {itemColumns.length > 0 && <th colSpan={itemColumns.length}>Cost items from Written Agreement</th>}
                  {referenceColumns.length > 0 && <th colSpan={referenceColumns.length}>Funding references</th>}
                  <th colSpan="4">Agreement calculation</th>
                  <th colSpan="2">ILR vs Written Agreement</th>
                </tr>
                <tr>
                  {ilrColumns.length > 0 && <th>ILR funding date</th>}
                  {ilrColumns.map((column) => <th key={column.key}>{column.label}</th>)}
                  {ilrColumns.length > 0 && <th>ILR total</th>}
                  {itemColumns.map((column) => <th key={column.key}>{column.label}</th>)}
                  {referenceColumns.map((column) => <th key={column.key}>{column.label}</th>)}
                  <th>Calculated total</th>
                  <th>JSON total</th>
                  <th>Difference</th>
                  <th className="funding-validation-cell">Agreement check</th>
                  <th>Difference</th>
                  <th className="funding-validation-cell">Totals check</th>
                </tr>
              </thead>
              <tbody>
                {data?.rows?.map((agreement) => (
                  <tr key={agreement.row_key}>
                    <td className="sticky-learner">
                      <div className="person-cell comparison-person">
                        <span className="avatar">{agreement.full_name?.trim()?.[0]?.toUpperCase() || "?"}</span>
                        <div><strong>{agreement.full_name}</strong><small>{agreement.email || `Learner #${agreement.learner_id}`}</small></div>
                      </div>
                    </td>
                    <td className="sticky-programme">
                      <div className="funding-programme-cell">
                        <span className="comparison-programme">{agreement.program_name || "—"}</span>
                        <small>{agreement.ilr_program_start_date ? `ILR start: ${formatDate(agreement.ilr_program_start_date)}` : "No ILR start date"}</small>
                      </div>
                    </td>
                    <td className="sticky-status"><ProgramStatusBadge status={agreement.program_status} /></td>
                    <td className="sticky-agreement">
                      <div className="funding-agreement-cell">
                        <strong>{agreement.document_name || "Missing"}</strong>
                        {agreement.document_id ? <small>Document #{agreement.source_document_id || agreement.document_id}</small> : <small>No Written Agreement found</small>}
                        {agreement.document_id && <span>{agreement.agreement_date ? formatDate(agreement.agreement_date) : "No date"}</span>}
                        {agreement.file && <a href={agreement.file} target="_blank" rel="noreferrer" title="Open Written Agreement"><ExternalLink size={13} /> Open</a>}
                      </div>
                    </td>
                    {ilrColumns.length > 0 && <td><span className="ilr-finance-date">{agreement.ilr_finance_date ? formatDate(agreement.ilr_finance_date) : "—"}</span></td>}
                    {ilrColumns.map((column) => (
                      <td key={column.key}>
                        <span className={`funding-value ilr-value ${agreement.ilr_finance_items?.[column.key] == null ? "is-blank" : ""}`}>
                          {formatCurrency(agreement.ilr_finance_items?.[column.key])}
                        </span>
                      </td>
                    ))}
                    {ilrColumns.length > 0 && <td><span className="funding-total ilr-total">{formatCurrency(agreement.ilr_finance_total)}</span></td>}
                    {itemColumns.map((column) => (
                      <td key={column.key}>
                        <span className={`funding-value ${agreement.cost_items?.[column.key] == null ? "is-blank" : ""}`}>
                          {formatCurrency(agreement.cost_items?.[column.key])}
                        </span>
                      </td>
                    ))}
                    {referenceColumns.map((column) => (
                      <td key={column.key}><span className="funding-reference">{formatCurrency(agreement[column.key])}</span></td>
                    ))}
                    <td><span className="funding-total calculated">{formatCurrency(agreement.calculated_total)}</span></td>
                    <td><span className="funding-total json-total">{formatCurrency(agreement.json_total)}</span></td>
                    <td><span className={`funding-difference ${agreement.difference != null && Number(agreement.difference) === 0 ? "is-zero" : "has-difference"}`}>{formatCurrency(agreement.difference)}</span></td>
                    <td className="funding-validation-cell">
                      <div className={`comparison-result ${agreement.agreement_comparison_status === "matched" ? "matched" : agreement.agreement_comparison_status === "missing" ? "missing" : "not-matched"}`}>
                        {agreement.agreement_comparison_status === "matched" ? <CircleCheckBig size={16} /> : agreement.agreement_comparison_status === "missing" ? <CircleAlert size={16} /> : <CircleX size={16} />}
                        <span>
                          <strong>{agreement.agreement_comparison_status === "matched" ? "Correct" : agreement.agreement_comparison_status === "missing" ? "Missing" : "Incorrect"}</strong>
                          <small>{agreement.agreement_comparison_reason}</small>
                        </span>
                      </div>
                    </td>
                    <td><span className={`funding-difference ${agreement.ilr_agreement_difference != null && Number(agreement.ilr_agreement_difference) === 0 ? "is-zero" : "has-difference"}`}>{formatCurrency(agreement.ilr_agreement_difference)}</span></td>
                    <td className="funding-validation-cell">
                      <div className={`comparison-result ${agreement.ilr_agreement_status === "matched" ? "matched" : agreement.ilr_agreement_status === "missing" ? "missing" : "not-matched"}`}>
                        {agreement.ilr_agreement_status === "matched" ? <CircleCheckBig size={16} /> : agreement.ilr_agreement_status === "missing" ? <CircleAlert size={16} /> : <CircleX size={16} />}
                        <span>
                          <strong>{agreement.ilr_agreement_status === "matched" ? "Matched" : agreement.ilr_agreement_status === "missing" ? "Missing" : "Mismatched"}</strong>
                          <small>{agreement.ilr_agreement_reason}</small>
                        </span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!loading && !data?.rows?.length && (
              <div className="empty-state">
                <div><Search size={25} /></div>
                <strong>No agreements found</strong>
                <p>Try a different search term or validation filter.</p>
              </div>
            )}
          </div>
        )}

        {!error && (
          <div className="pagination">
            <span>Page <b>{pagination.page}</b> of <b>{pagination.pages}</b></span>
            <div>
              <button onClick={() => setPage((current) => Math.max(current - 1, 1))} disabled={page <= 1 || loading}>
                <ArrowLeft size={17} /> Previous
              </button>
              <button onClick={() => setPage((current) => Math.min(current + 1, pagination.pages))} disabled={page >= pagination.pages || loading}>
                Next <ArrowRight size={17} />
              </button>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

function PriorLearningPage() {
  const [data, setData] = useState(null);
  const [search, setSearch] = useState("");
  const [comparisonFilter, setComparisonFilter] = useState("all");
  const [programStatus, setProgramStatus] = useState("all");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const summary = data?.summary ?? {};
  const queryString = useMemo(() => {
    const params = new URLSearchParams({ filter: comparisonFilter });
    params.set("programStatus", programStatus);
    if (search.trim()) params.set("search", search.trim());
    return params.toString();
  }, [search, comparisonFilter, programStatus]);

  async function loadPriorLearning() {
    setLoading(true);
    setError("");
    try {
      const response = await fetch(apiUrl(`/api/prior-learning/?${queryString}`), {
        cache: "no-store",
      });
      const nextData = await getResponseMessage(response, "Unable to load prior-learning data.");
      setData(nextData);
    } catch (loadError) {
      setError(loadError.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const timeout = setTimeout(() => loadPriorLearning(), search ? 350 : 0);
    return () => clearTimeout(timeout);
    // queryString contains the complete search and filter state.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queryString]);

  function changeFilter(value) {
    setComparisonFilter(value);
  }

  function changeProgramStatus(value) {
    setProgramStatus(value);
  }

  function comparisonResult(status, reason, matchedLabel = "Matched") {
    const tone = status === "matched" ? "matched" : status === "missing" ? "missing" : "not-matched";
    const Icon = status === "matched" ? CircleCheckBig : status === "missing" ? CircleAlert : CircleX;
    return (
      <div className={`comparison-result ${tone}`}>
        <Icon size={16} />
        <span>
          <strong>{status === "matched" ? matchedLabel : status === "missing" ? "Missing" : "Mismatched"}</strong>
          <small>{reason}</small>
        </span>
      </div>
    );
  }

  return (
    <div className="page comparison-page prior-learning-page">
      <section className="hero">
        <div>
          <span className="eyebrow">PRIOR LEARNING AUDIT</span>
          <h1>Prior Learning Review</h1>
          <p>Review the selected learners' hours and funding across ILR and Aptem records.</p>
        </div>
      </section>

      <section className="summary-grid comparison-summary-grid funding-summary-grid">
        <SummaryCard icon={UsersRound} label="Selected learners" value={summary.learners} detail="Named learners reviewed" tone="blue" onClick={() => changeFilter("all")} active={comparisonFilter === "all"} />
        <SummaryCard icon={CircleCheckBig} label="Hours matched" value={summary.hoursMatched} detail="ILR equals Aptem planned" tone="green" onClick={() => changeFilter("hours-matched")} active={comparisonFilter === "hours-matched"} />
        <SummaryCard icon={CircleX} label="Hours mismatched" value={summary.hoursMismatched} detail="ILR and Aptem planned differ" tone="orange" onClick={() => changeFilter("hours-mismatched")} active={comparisonFilter === "hours-mismatched"} />
        <SummaryCard icon={CircleCheckBig} label="Funding matched" value={summary.fundingMatched} detail="ILR equals Agreement total" tone="green" onClick={() => changeFilter("funding-matched")} active={comparisonFilter === "funding-matched"} />
        <SummaryCard icon={CircleX} label="Funding mismatched" value={summary.fundingMismatched} detail="ILR and Agreement totals differ" tone="orange" onClick={() => changeFilter("funding-mismatched")} active={comparisonFilter === "funding-mismatched"} />
        <SummaryCard icon={CircleAlert} label="Missing data" value={summary.missingValues} detail="Hours or funding is incomplete" tone="purple" onClick={() => changeFilter("missing")} active={comparisonFilter === "missing"} />
      </section>

      <section className="content-card comparison-card funding-card prior-learning-card">
        <div className="content-heading">
          <div>
            <h2>ILR and Aptem details</h2>
            <p>{formatNumber(data?.rows?.length)} learners shown</p>
          </div>
          <div className="content-actions">
            <RefetchWrittenAgreementsButton scope="prior-learning" onComplete={loadPriorLearning} />
            <button className="refresh-button" onClick={() => loadPriorLearning()} disabled={loading}>
              <RefreshCw size={16} className={loading ? "spin" : ""} /> Refresh
            </button>
          </div>
        </div>

        <div className="comparison-toolbar">
          <label className="search-box">
            <Search size={18} />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search by learner, email, programme or ILR reference..."
            />
            {search && (
              <button type="button" onClick={() => setSearch("")} aria-label="Clear search">
                <X size={16} />
              </button>
            )}
          </label>
          <ProgramStatusFilter value={programStatus} statuses={data?.programStatuses} onChange={changeProgramStatus} />
        </div>

        {error ? (
          <div className="state-panel error-state">
            <CircleAlert size={26} />
            <div><strong>Could not load prior-learning data</strong><p>{error}</p></div>
            <button onClick={() => loadPriorLearning()}>Try again</button>
          </div>
        ) : (
          <div className={`table-wrap comparison-table-wrap funding-table-wrap prior-learning-table-wrap ${loading ? "is-loading" : ""}`}>
            {loading && <div className="loading-layer"><LoaderCircle size={26} className="spin" /></div>}
            <table className="comparison-table funding-comparison-table prior-learning-table">
              <thead>
                <tr className="funding-group-row">
                  <th className="sticky-learner" rowSpan="2">Learner</th>
                  <th className="sticky-programme" rowSpan="2">Programme</th>
                  <th className="sticky-status" rowSpan="2">Program status</th>
                  <th className="prior-hours-group" colSpan="7">Hours</th>
                  <th className="prior-funding-group" colSpan="11">Funding</th>
                </tr>
                <tr>
                  <th>ILR planned</th>
                  <th>Aptem minimum</th>
                  <th>Aptem planned</th>
                  <th>Minimum − planned</th>
                  <th>Training Plan</th>
                  <th>Apprenticeship Agreement</th>
                  <th className="funding-validation-cell">Hours check</th>
                  <th>ILR TNP date</th>
                  <th>ILR training</th>
                  <th>ILR EPA</th>
                  <th>ILR total</th>
                  <th>Agreement actual funding</th>
                  <th>Agreement EPA</th>
                  <th>Agreement total</th>
                  <th>Funding band maximum</th>
                  <th>Band − Agreement</th>
                  <th>ILR − Agreement</th>
                  <th className="funding-validation-cell">Funding check</th>
                </tr>
              </thead>
              <tbody>
                {data?.rows?.map((learner) => (
                  <tr key={learner.row_key}>
                    <td className="sticky-learner">
                      <div className="person-cell comparison-person">
                        <span className="avatar">{learner.full_name?.trim()?.[0]?.toUpperCase() || "?"}</span>
                        <div><strong>{learner.full_name}</strong><small>{learner.email || learner.learn_ref_number}</small></div>
                      </div>
                    </td>
                    <td className="sticky-programme">
                      <div className="funding-programme-cell">
                        <span className="comparison-programme">{learner.program_name || "Not available"}</span>
                        <small>{learner.learn_start_date ? `ILR start: ${formatDate(learner.learn_start_date)}` : learner.learn_ref_number}</small>
                      </div>
                    </td>
                    <td className="sticky-status"><ProgramStatusBadge status={learner.program_status} /></td>
                    <td><span className={`hours-value ${learner.ilr_planned_hours == null ? "is-missing" : ""}`}>{formatHours(learner.ilr_planned_hours)}</span></td>
                    <td><span className={`hours-value source-minimum ${learner.aptem_minimum_hours == null ? "is-missing" : ""}`}>{formatHours(learner.aptem_minimum_hours)}</span></td>
                    <td><span className={`hours-value ${learner.aptem_planned_hours == null ? "is-missing" : ""}`}>{formatHours(learner.aptem_planned_hours)}</span></td>
                    <td><span className={`hours-value hours-difference ${learner.minimum_planned_difference == null ? "is-missing" : ""}`}>{formatHours(learner.minimum_planned_difference)}</span></td>
                    <td><span className={`hours-value ${learner.training_plan_planned_hours == null ? "is-missing" : ""}`}>{formatHours(learner.training_plan_planned_hours)}</span></td>
                    <td><span className={`hours-value ${learner.apprenticeship_agreement_planned_hours == null ? "is-missing" : ""}`}>{formatHours(learner.apprenticeship_agreement_planned_hours)}</span></td>
                    <td className="funding-validation-cell">{comparisonResult(learner.hours_status, learner.hours_reason)}</td>
                    <td><span className="ilr-finance-date">{learner.ilr_finance_date ? formatDate(learner.ilr_finance_date) : "No date"}</span></td>
                    <td><span className="funding-value ilr-value">{formatCurrency(learner.ilr_training_amount)}</span></td>
                    <td><span className="funding-value ilr-value">{formatCurrency(learner.ilr_epa_amount)}</span></td>
                    <td><span className="funding-total ilr-total">{formatCurrency(learner.ilr_finance_total)}</span></td>
                    <td><span className="funding-value">{formatCurrency(learner.agreement_actual_funding)}</span></td>
                    <td><span className="funding-value">{formatCurrency(learner.agreement_epa)}</span></td>
                    <td>
                      <div className="prior-agreement-total">
                        <span className="funding-total json-total">{formatCurrency(learner.agreement_total)}</span>
                        {learner.written_agreement_file && <a href={learner.written_agreement_file} target="_blank" rel="noreferrer"><ExternalLink size={12} /> Open</a>}
                      </div>
                    </td>
                    <td><span className="funding-reference">{formatCurrency(learner.agreement_band_maximum)}</span></td>
                    <td><span className="funding-difference">{formatCurrency(learner.funding_reduction_from_band)}</span></td>
                    <td><span className={`funding-difference ${learner.funding_difference != null && Number(learner.funding_difference) === 0 ? "is-zero" : "has-difference"}`}>{formatCurrency(learner.funding_difference)}</span></td>
                    <td className="funding-validation-cell">{comparisonResult(learner.funding_status, learner.funding_reason)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!loading && !data?.rows?.length && (
              <div className="empty-state">
                <div><Search size={25} /></div>
                <strong>No learners found</strong>
                <p>Try a different search term or comparison filter.</p>
              </div>
            )}
          </div>
        )}
      </section>
    </div>
  );
}

function EndpointAssessmentPage() {
  const [data, setData] = useState(null);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [timelineFilter, setTimelineFilter] = useState("all");
  const [programStatus, setProgramStatus] = useState("all");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const summary = data?.summary ?? {};
  const pagination = data?.pagination ?? { page: 1, pages: 1, total: 0 };
  const queryString = useMemo(() => {
    const params = new URLSearchParams({
      page: String(page),
      filter: timelineFilter,
      programStatus,
    });
    if (search.trim()) params.set("search", search.trim());
    return params.toString();
  }, [page, search, timelineFilter, programStatus]);

  async function loadEndpointAssessments() {
    setLoading(true);
    setError("");
    try {
      const response = await fetch(apiUrl(`/api/endpoint-assessments/?${queryString}`), {
        cache: "no-store",
      });
      const nextData = await getResponseMessage(response, "Unable to load endpoint-assessment data.");
      setData(nextData);
    } catch (loadError) {
      setError(loadError.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const timeout = setTimeout(() => loadEndpointAssessments(), search ? 350 : 0);
    return () => clearTimeout(timeout);
    // queryString contains the complete search, page and filter state.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queryString]);

  function changeFilter(value) {
    setPage(1);
    setTimelineFilter(value);
  }

  function changeSearch(value) {
    setPage(1);
    setSearch(value);
  }

  function changeProgramStatus(value) {
    setPage(1);
    setProgramStatus(value);
  }

  function timelineResult(learner) {
    const status = learner.timeline_status;
    const tone = status === "completed" ? "matched" : status === "in-progress" ? "in-progress" : status === "missing" ? "missing" : "not-matched";
    const Icon = status === "completed" ? CircleCheckBig : status === "overdue" ? CircleAlert : CalendarDays;
    const label = status === "completed" ? "Actual end recorded" : status === "in-progress" ? "In progress" : status === "overdue" ? "Past planned end" : "Missing dates";
    return (
      <div className={`comparison-result endpoint-result ${tone}`}>
        <Icon size={16} />
        <span><strong>{label}</strong><small>{learner.timeline_reason}</small></span>
      </div>
    );
  }

  return (
    <div className="page comparison-page endpoint-assessment-page">
      <section className="hero">
        <div>
          <span className="eyebrow">ENDPOINT ASSESSMENT</span>
          <h1>Endpoint Assessment Dates</h1>
          <p>Review ILR programme start, planned end and actual end dates for every learner.</p>
        </div>
      </section>

      <section className="summary-grid comparison-summary-grid endpoint-summary-grid">
        <SummaryCard icon={UsersRound} label="ILR learners" value={summary.learners} detail="Latest programme per learner" tone="blue" onClick={() => changeFilter("all")} active={timelineFilter === "all"} />
        <SummaryCard icon={CircleCheckBig} label="Actual end recorded" value={summary.completed} detail="ILR actual end is available" tone="green" onClick={() => changeFilter("completed")} active={timelineFilter === "completed"} />
        <SummaryCard icon={CalendarDays} label="In progress" value={summary.inProgress} detail="Before the planned end date" tone="blue" onClick={() => changeFilter("in-progress")} active={timelineFilter === "in-progress"} />
        <SummaryCard icon={CircleAlert} label="Past planned end" value={summary.overdue} detail="No actual end date recorded" tone="orange" onClick={() => changeFilter("overdue")} active={timelineFilter === "overdue"} />
        <SummaryCard icon={CircleAlert} label="Missing dates" value={summary.missingDates} detail="Start or planned end is missing" tone="purple" onClick={() => changeFilter("missing")} active={timelineFilter === "missing"} />
      </section>

      <section className="content-card comparison-card endpoint-assessment-card">
        <div className="content-heading">
          <div>
            <h2>Learner endpoint timeline</h2>
            <p>{formatNumber(pagination.total)} learners · one learner per row</p>
          </div>
          <button className="refresh-button" onClick={() => loadEndpointAssessments()} disabled={loading}>
            <RefreshCw size={16} className={loading ? "spin" : ""} /> Refresh
          </button>
        </div>

        <div className="comparison-toolbar">
          <label className="search-box">
            <Search size={18} />
            <input
              value={search}
              onChange={(event) => changeSearch(event.target.value)}
              placeholder="Search by learner, email, programme or ILR reference..."
            />
            {search && <button type="button" onClick={() => changeSearch("")} aria-label="Clear search"><X size={16} /></button>}
          </label>
          <ProgramStatusFilter value={programStatus} statuses={data?.programStatuses} onChange={changeProgramStatus} />
        </div>

        {error ? (
          <div className="state-panel error-state">
            <CircleAlert size={26} />
            <div><strong>Could not load endpoint-assessment data</strong><p>{error}</p></div>
            <button onClick={() => loadEndpointAssessments()}>Try again</button>
          </div>
        ) : (
          <div className={`table-wrap comparison-table-wrap endpoint-assessment-table-wrap ${loading ? "is-loading" : ""}`}>
            {loading && <div className="loading-layer"><LoaderCircle size={26} className="spin" /></div>}
            <table className="comparison-table endpoint-assessment-table">
              <thead>
                <tr>
                  <th>Learner</th>
                  <th>Programme</th>
                  <th>Program status</th>
                  <th>ILR start date</th>
                  <th>ILR planned end date</th>
                  <th>ILR actual end date</th>
                  <th>Timeline status</th>
                </tr>
              </thead>
              <tbody>
                {data?.rows?.map((learner) => (
                  <tr key={learner.row_key}>
                    <td>
                      <div className="person-cell comparison-person">
                        <span className="avatar">{learner.full_name?.trim()?.[0]?.toUpperCase() || "?"}</span>
                        <div><strong>{learner.full_name}</strong><small>{learner.email || learner.learn_ref_number}</small></div>
                      </div>
                    </td>
                    <td><span className="comparison-programme">{learner.program_name || "Not available"}</span></td>
                    <td><ProgramStatusBadge status={learner.program_status} /></td>
                    <td><span className={`endpoint-date-value ${learner.learn_start_date ? "" : "is-missing"}`}>{learner.learn_start_date ? formatDate(learner.learn_start_date) : "Missing"}</span></td>
                    <td><span className={`endpoint-date-value planned ${learner.learn_plan_end_date ? "" : "is-missing"}`}>{learner.learn_plan_end_date ? formatDate(learner.learn_plan_end_date) : "Missing"}</span></td>
                    <td><span className={`endpoint-date-value actual ${learner.learn_actual_end_date ? "is-recorded" : "is-missing"}`}>{learner.learn_actual_end_date ? formatDate(learner.learn_actual_end_date) : "Not recorded"}</span></td>
                    <td>{timelineResult(learner)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!loading && !data?.rows?.length && (
              <div className="empty-state">
                <div><Search size={25} /></div>
                <strong>No learners found</strong>
                <p>Try a different search term or timeline filter.</p>
              </div>
            )}
          </div>
        )}

        {!error && (
          <div className="pagination">
            <span>Page <b>{pagination.page}</b> of <b>{pagination.pages}</b></span>
            <div>
              <button onClick={() => setPage((current) => Math.max(current - 1, 1))} disabled={page <= 1 || loading}><ArrowLeft size={17} /> Previous</button>
              <button onClick={() => setPage((current) => Math.min(current + 1, pagination.pages))} disabled={page >= pagination.pages || loading}>Next <ArrowRight size={17} /></button>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

function MonthlyHoursPage() {
  const [data, setData] = useState(null);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [year, setYear] = useState(String(new Date().getFullYear()));
  const [hoursFilter, setHoursFilter] = useState("all");
  const [programStatus, setProgramStatus] = useState("all");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const summary = data?.summary ?? {};
  const pagination = data?.pagination ?? { page: 1, pages: 1, total: 0 };
  const queryString = useMemo(() => {
    const params = new URLSearchParams({
      page: String(page),
      year,
      filter: hoursFilter,
      programStatus,
    });
    if (search.trim()) params.set("search", search.trim());
    return params.toString();
  }, [page, year, hoursFilter, programStatus, search]);

  async function loadMonthlyHours() {
    setLoading(true);
    setError("");
    try {
      const response = await fetch(apiUrl(`/api/monthly-hours/?${queryString}`), {
        cache: "no-store",
      });
      const nextData = await getResponseMessage(response, "Unable to load monthly hours.");
      setData(nextData);
    } catch (loadError) {
      setError(loadError.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const timeout = setTimeout(() => loadMonthlyHours(), search ? 350 : 0);
    return () => clearTimeout(timeout);
    // queryString contains the complete search, page and filter state.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queryString]);

  function changeSearch(value) {
    setPage(1);
    setSearch(value);
  }

  function changeYear(value) {
    setPage(1);
    setYear(value);
  }

  function changeHoursFilter(value) {
    setPage(1);
    setHoursFilter(value);
  }

  function changeProgramStatus(value) {
    setPage(1);
    setProgramStatus(value);
  }

  return (
    <div className="page comparison-page monthly-hours-page">
      <section className="hero">
        <div>
          <span className="eyebrow">LEARNING ACTIVITY</span>
          <h1>Monthly Learner Hours</h1>
          <p>Review planned and submitted hours for every learner, month by month.</p>
        </div>
      </section>

      <section className="summary-grid comparison-summary-grid monthly-hours-summary-grid">
        <SummaryCard icon={UsersRound} label="Learners" value={summary.learners} detail={`Available in ${year}`} tone="blue" onClick={() => changeHoursFilter("all")} active={hoursFilter === "all"} />
        <SummaryCard icon={CalendarDays} label="Learners with hours" value={summary.withHours} detail="Planned or submitted activity" tone="green" onClick={() => changeHoursFilter("with-hours")} active={hoursFilter === "with-hours"} />
        <SummaryCard icon={Clock3} label="Planned hours" value={summary.plannedHours} detail={`Total planned in ${year}`} tone="purple" />
        <SummaryCard icon={CircleCheckBig} label="Completed hours" value={summary.completedHours} detail={`Total submitted in ${year}`} tone="green" />
      </section>

      <section className="content-card comparison-card monthly-hours-card">
        <div className="content-heading">
          <div>
            <h2>Learner monthly hours</h2>
            <p>{formatNumber(pagination.total)} learners · one learner per row</p>
          </div>
          <button className="refresh-button" onClick={() => loadMonthlyHours()} disabled={loading}>
            <RefreshCw size={16} className={loading ? "spin" : ""} /> Refresh
          </button>
        </div>

        <div className="comparison-toolbar monthly-hours-toolbar">
          <label className="search-box">
            <Search size={18} />
            <input
              value={search}
              onChange={(event) => changeSearch(event.target.value)}
              placeholder="Search by learner, programme or learner ID..."
            />
            {search && <button type="button" onClick={() => changeSearch("")} aria-label="Clear search"><X size={16} /></button>}
          </label>
          <YearFilter value={year} years={data?.availableYears ?? [Number(year)]} onChange={changeYear} />
          <ProgramStatusFilter value={programStatus} statuses={data?.programStatuses} onChange={changeProgramStatus} />
        </div>

        {error ? (
          <div className="state-panel error-state">
            <CircleAlert size={26} />
            <div><strong>Could not load monthly hours</strong><p>{error}</p></div>
            <button onClick={() => loadMonthlyHours()}>Try again</button>
          </div>
        ) : (
          <div className={`table-wrap comparison-table-wrap monthly-hours-table-wrap ${loading ? "is-loading" : ""}`}>
            {loading && <div className="loading-layer"><LoaderCircle size={26} className="spin" /></div>}
            <table className="comparison-table monthly-hours-table">
              <thead>
                <tr className="monthly-hours-group-row">
                  <th className="monthly-sticky-learner" rowSpan="2">Learner</th>
                  <th className="monthly-sticky-programme" rowSpan="2">Programme</th>
                  <th className="monthly-sticky-status" rowSpan="2">Program status</th>
                  <th className="monthly-year-total" rowSpan="2">Year planned</th>
                  <th className="monthly-year-total" rowSpan="2">Year completed</th>
                  {data?.months?.map((month) => (
                    <th className="monthly-month-heading" colSpan="2" key={month.key}>
                      <strong>{month.label}</strong><small>{year}</small>
                    </th>
                  ))}
                </tr>
                <tr className="monthly-hours-subhead-row">
                  {data?.months?.map((month) => (
                    <Fragment key={month.key}>
                      <th>Planned</th>
                      <th>Completed</th>
                    </Fragment>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data?.rows?.map((learner) => (
                  <tr key={learner.row_key}>
                    <td className="monthly-sticky-learner">
                      <div className="person-cell comparison-person">
                        <span className="avatar">{learner.full_name?.trim()?.[0]?.toUpperCase() || "?"}</span>
                        <div><strong>{learner.full_name || `Learner #${learner.learner_id}`}</strong><small>{learner.email || `Learner #${learner.learner_id}`}</small></div>
                      </div>
                    </td>
                    <td className="monthly-sticky-programme"><span className="comparison-programme">{learner.program_name || "Not available"}</span></td>
                    <td className="monthly-sticky-status"><ProgramStatusBadge status={learner.program_status} /></td>
                    <td><span className={`monthly-total-value planned ${learner.planned_total == null ? "is-empty" : ""}`}>{learner.planned_total == null ? "—" : formatHours(learner.planned_total)}</span></td>
                    <td><span className={`monthly-total-value completed ${learner.completed_total == null ? "is-empty" : ""}`}>{learner.completed_total == null ? "—" : formatHours(learner.completed_total)}</span></td>
                    {learner.months?.map((month) => (
                      <Fragment key={month.key}>
                        <td><span className={`monthly-hour-value planned ${month.planned == null ? "is-empty" : ""}`}>{month.planned == null ? "—" : formatHours(month.planned)}</span></td>
                        <td><span className={`monthly-hour-value completed ${month.completed == null ? "is-empty" : ""}`}>{month.completed == null ? "—" : formatHours(month.completed)}</span></td>
                      </Fragment>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            {!loading && !data?.rows?.length && (
              <div className="empty-state">
                <div><Search size={25} /></div>
                <strong>No learners found</strong>
                <p>Try another year, search term or program status.</p>
              </div>
            )}
          </div>
        )}

        {!error && (
          <div className="pagination">
            <span>Page <b>{pagination.page}</b> of <b>{pagination.pages}</b></span>
            <div>
              <button onClick={() => setPage((current) => Math.max(current - 1, 1))} disabled={page <= 1 || loading}><ArrowLeft size={17} /> Previous</button>
              <button onClick={() => setPage((current) => Math.min(current + 1, pagination.pages))} disabled={page >= pagination.pages || loading}>Next <ArrowRight size={17} /></button>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

function SkillsRadarPage() {
  const [data, setData] = useState(null);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [radarFilter, setRadarFilter] = useState("all");
  const [programStatus, setProgramStatus] = useState("all");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const summary = data?.summary ?? {};
  const pagination = data?.pagination ?? { page: 1, pages: 1, total: 0 };
  const queryString = useMemo(() => {
    const params = new URLSearchParams({
      page: String(page),
      filter: radarFilter,
      programStatus,
    });
    if (search.trim()) params.set("search", search.trim());
    return params.toString();
  }, [page, radarFilter, programStatus, search]);

  async function loadSkillsRadar() {
    setLoading(true);
    setError("");
    try {
      const response = await fetch(apiUrl(`/api/skills-radar/?${queryString}`), {
        cache: "no-store",
      });
      const nextData = await getResponseMessage(response, "Unable to load Skills Radar data.");
      setData(nextData);
    } catch (loadError) {
      setError(loadError.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const timeout = setTimeout(() => loadSkillsRadar(), search ? 350 : 0);
    return () => clearTimeout(timeout);
    // queryString contains the complete search, page and filter state.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queryString]);

  function changeSearch(value) {
    setPage(1);
    setSearch(value);
  }

  function changeRadarFilter(value) {
    setPage(1);
    setRadarFilter(value);
  }

  function changeProgramStatus(value) {
    setPage(1);
    setProgramStatus(value);
  }

  return (
    <div className="page comparison-page skills-radar-page">
      <section className="hero">
        <div>
          <span className="eyebrow">SKILLS &amp; FUNDING AUDIT</span>
          <h1>Skills Radar Overview</h1>
          <p>Review every ILR learner's Skills Radar score, planned hours, reductions and funding.</p>
        </div>
      </section>

      <section className="summary-grid comparison-summary-grid skills-radar-summary-grid">
        <SummaryCard icon={UsersRound} label="ILR learners" value={summary.learners} detail="One learner per row" tone="blue" onClick={() => changeRadarFilter("all")} active={radarFilter === "all"} />
        <SummaryCard icon={Radar} label="Radar assessed" value={summary.radarAssessed} detail="Learners with a score" tone="green" onClick={() => changeRadarFilter("assessed")} active={radarFilter === "assessed"} />
        <SummaryCard icon={BadgePoundSterling} label="Funding reductions" value={summary.fundingReduced} detail="Oldest versus latest TNP" tone="orange" onClick={() => changeRadarFilter("reduced")} active={radarFilter === "reduced"} />
        <SummaryCard icon={BadgePoundSterling} label="ILR funding" value={summary.fundingAvailable} detail="Learners with TNP funding" tone="purple" />
      </section>

      <section className="content-card comparison-card skills-radar-card">
        <div className="content-heading">
          <div>
            <h2>Learner Skills Radar and RPL</h2>
            <p>{formatNumber(pagination.total)} learners · one learner per row</p>
          </div>
          <button className="refresh-button" onClick={() => loadSkillsRadar()} disabled={loading}>
            <RefreshCw size={16} className={loading ? "spin" : ""} /> Refresh
          </button>
        </div>

        <div className="comparison-toolbar">
          <label className="search-box">
            <Search size={18} />
            <input
              value={search}
              onChange={(event) => changeSearch(event.target.value)}
              placeholder="Search by learner, programme or learner ID..."
            />
            {search && <button type="button" onClick={() => changeSearch("")} aria-label="Clear search"><X size={16} /></button>}
          </label>
          <ProgramStatusFilter value={programStatus} statuses={data?.programStatuses} onChange={changeProgramStatus} />
        </div>

        {error ? (
          <div className="state-panel error-state">
            <CircleAlert size={26} />
            <div><strong>Could not load Skills Radar data</strong><p>{error}</p></div>
            <button onClick={() => loadSkillsRadar()}>Try again</button>
          </div>
        ) : (
          <div className={`table-wrap comparison-table-wrap skills-radar-table-wrap ${loading ? "is-loading" : ""}`}>
            {loading && <div className="loading-layer"><LoaderCircle size={26} className="spin" /></div>}
            <table className="comparison-table skills-radar-table">
              <thead>
                <tr className="skills-radar-group-row">
                  <th rowSpan="2">Learner</th>
                  <th rowSpan="2">Programme</th>
                  <th rowSpan="2">Program status</th>
                  <th className="hours-group" colSpan="1">ILR planned hours</th>
                  <th className="radar-group" colSpan="2">Skills Radar</th>
                  <th className="funding-group" colSpan="6">ILR TNP funding history</th>
                </tr>
                <tr className="skills-radar-subhead-row">
                  <th>Planned hours (ILR)</th>
                  <th>Score</th>
                  <th>Assessed</th>
                  <th>Original TNP</th>
                  <th>Training</th>
                  <th>EPA</th>
                  <th>Latest TNP</th>
                  <th>Reduced by</th>
                  <th>Reduction</th>
                </tr>
              </thead>
              <tbody>
                {data?.rows?.map((learner) => (
                  <tr key={learner.row_key}>
                    <td>
                      <div className="person-cell comparison-person">
                        <span className="avatar">{learner.full_name?.trim()?.[0]?.toUpperCase() || "?"}</span>
                        <div><strong>{learner.full_name || `Learner #${learner.learner_id}`}</strong><small>{learner.email || `Learner #${learner.learner_id}`}</small></div>
                      </div>
                    </td>
                    <td><span className="comparison-programme">{learner.program_name || "Not available"}</span></td>
                    <td><ProgramStatusBadge status={learner.program_status} /></td>
                    <td><span className={`hours-value ${learner.ilr_planned_hours == null ? "is-missing" : ""}`}>{learner.ilr_planned_hours == null ? "Missing" : `${formatHours(learner.ilr_planned_hours)} hrs`}</span></td>
                    <td>
                      {learner.score_percentage == null ? (
                        <span className="radar-score is-missing">Missing</span>
                      ) : (
                        <span className="radar-score"><Radar size={14} /> {formatHours(learner.score_percentage)}%</span>
                      )}
                    </td>
                    <td><span className="radar-assessed-count">{learner.assessed_items ?? 0} / {learner.total_items ?? 0}</span></td>
                    <td><span className="funding-value" title={`${learner.funding_snapshot_count || 0} dated TNP snapshot(s)`}>{formatCurrency(learner.original_ilr_funding)}</span></td>
                    <td><span className="funding-value">{formatCurrency(learner.ilr_training_amount)}</span></td>
                    <td><span className="funding-value">{formatCurrency(learner.ilr_epa_amount)}</span></td>
                    <td><span className="funding-total">{formatCurrency(learner.ilr_finance_total)}</span></td>
                    <td><span className={`reduction-value ${learner.has_funding_reduction ? "has-reduction" : ""}`}>{learner.funding_reduction == null ? "Missing" : formatCurrency(learner.funding_reduction)}</span></td>
                    <td><span className={`reduction-value ${learner.has_funding_reduction ? "has-reduction" : ""}`}>{learner.funding_reduction_percentage == null ? "Missing" : `${formatHours(learner.funding_reduction_percentage)}%`}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!loading && !data?.rows?.length && (
              <div className="empty-state">
                <div><Search size={25} /></div>
                <strong>No learners found</strong>
                <p>Try another search, status or summary filter.</p>
              </div>
            )}
          </div>
        )}

        {!error && (
          <div className="pagination">
            <span>Page <b>{pagination.page}</b> of <b>{pagination.pages}</b></span>
            <div>
              <button onClick={() => setPage((current) => Math.max(current - 1, 1))} disabled={page <= 1 || loading}><ArrowLeft size={17} /> Previous</button>
              <button onClick={() => setPage((current) => Math.min(current + 1, pagination.pages))} disabled={page >= pagination.pages || loading}>Next <ArrowRight size={17} /></button>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

export default function App() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState(null);
  const [deleting, setDeleting] = useState(null);
  const [creating, setCreating] = useState(false);
  const [createForm, setCreateForm] = useState(emptyCreateForm);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [learnerScope, setLearnerScope] = useState("ilr");
  const [programStatus, setProgramStatus] = useState("all");
  const [scopeMenuOpen, setScopeMenuOpen] = useState(false);
  const [activePage, setActivePage] = useState(pageFromHash);
  const scopeMenuRef = useRef(null);

  const summary = data?.summary ?? {};
  const documentColumns = data?.documentColumns ?? [];
  const pagination = data?.pagination ?? { page: 1, pages: 1, total: 0 };

  const queryString = useMemo(() => {
    const params = new URLSearchParams();
    params.set("page", page);
    params.set("learnerScope", learnerScope);
    params.set("programStatus", programStatus);
    if (search.trim()) params.set("search", search.trim());
    return params.toString();
  }, [page, search, learnerScope, programStatus]);

  async function loadLearners({ quiet = false } = {}) {
    if (!quiet) setLoading(true);
    setError("");
    try {
      const response = await fetch(apiUrl(`/api/documents/?${queryString}`), {
        cache: "no-store",
      });
      const nextData = await getResponseMessage(response, "Unable to load data.");
      setData(nextData);
    } catch (loadError) {
      setError(loadError.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const timeout = setTimeout(() => loadLearners(), search ? 350 : 0);
    return () => clearTimeout(timeout);
    // queryString is the complete serialized filter state.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queryString]);

  useEffect(() => {
    if (!toast) return;
    const timeout = setTimeout(() => setToast(null), 3200);
    return () => clearTimeout(timeout);
  }, [toast]);

  useEffect(() => {
    function closeScopeMenu(event) {
      if (scopeMenuRef.current && !scopeMenuRef.current.contains(event.target)) {
        setScopeMenuOpen(false);
      }
    }

    function closeScopeMenuOnEscape(event) {
      if (event.key === "Escape") setScopeMenuOpen(false);
    }

    document.addEventListener("mousedown", closeScopeMenu);
    document.addEventListener("keydown", closeScopeMenuOnEscape);
    return () => {
      document.removeEventListener("mousedown", closeScopeMenu);
      document.removeEventListener("keydown", closeScopeMenuOnEscape);
    };
  }, []);

  useEffect(() => {
    function syncPageFromHash() {
      setActivePage(pageFromHash());
    }

    window.addEventListener("hashchange", syncPageFromHash);
    return () => window.removeEventListener("hashchange", syncPageFromHash);
  }, []);

  function changePage(nextPage) {
    setActivePage(nextPage);
    const pageHashes = {
      documents: "documents",
      comparison: "date-comparison",
      "hours-comparison": "hours-comparison",
      "monthly-hours": "monthly-hours",
      "skills-radar": "skills-radar",
      "funding-comparison": "funding-comparison",
      "prior-learning": "prior-learning",
      "endpoint-assessment": "endpoint-assessment",
    };
    window.location.hash = pageHashes[nextPage];
    setSidebarOpen(false);
  }

  function changeSearch(value) {
    setPage(1);
    setSearch(value);
  }

  function changeLearnerScope(value) {
    setPage(1);
    setLearnerScope(value);
    setScopeMenuOpen(false);
  }

  function changeProgramStatus(value) {
    setPage(1);
    setProgramStatus(value);
  }

  function openEdit(document, learner) {
    setEditing({
      ...document,
      full_name: learner.full_name,
      email: learner.email,
      program_name: learner.program_name,
      learner_id: learner.learner_id,
    });
  }

  async function saveEdit(event) {
    event.preventDefault();
    setSaving(true);
    try {
      const response = await fetch(apiUrl(`/api/documents/${editing.id}/`), {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          file: editing.file,
          documentName: editing.document_name,
          category: editing.document_category,
          updatedTo: editing.updated_to || "",
        }),
      });
      const result = await getResponseMessage(response, "Unable to save changes.");
      setEditing(null);
      setToast({ tone: "success", message: result.message });
      await loadLearners({ quiet: true });
    } catch (saveError) {
      setToast({ tone: "error", message: saveError.message });
    } finally {
      setSaving(false);
    }
  }

  async function createDocument(event) {
    event.preventDefault();
    setSaving(true);
    try {
      const response = await fetch(apiUrl("/api/documents/"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(createForm),
      });
      const result = await getResponseMessage(response, "Unable to add the document.");
      setCreating(false);
      setCreateForm(emptyCreateForm);
      setToast({ tone: "success", message: result.message });
      setPage(1);
      await loadLearners({ quiet: true });
    } catch (saveError) {
      setToast({ tone: "error", message: saveError.message });
    } finally {
      setSaving(false);
    }
  }

  async function deleteDocument() {
    setSaving(true);
    try {
      const response = await fetch(apiUrl(`/api/documents/${deleting.id}/`), {
        method: "DELETE",
      });
      const result = await getResponseMessage(response, "Unable to delete the document.");
      setDeleting(null);
      setEditing(null);
      setToast({ tone: "success", message: result.message });
      await loadLearners({ quiet: true });
    } catch (deleteError) {
      setToast({ tone: "error", message: deleteError.message });
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className="app-shell">
      <aside className={`sidebar ${sidebarOpen ? "sidebar-open" : ""} ${sidebarCollapsed ? "sidebar-collapsed" : ""}`}>
        <button
          className="sidebar-collapse"
          type="button"
          onClick={() => setSidebarCollapsed((collapsed) => !collapsed)}
          aria-label={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          title={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {sidebarCollapsed ? <PanelLeftOpen size={16} /> : <PanelLeftClose size={16} />}
        </button>
        <div className="brand">
          <div className="brand-mark"><Files size={22} /></div>
          <div className="brand-copy"><strong>Aptem</strong><span>Documents</span></div>
        </div>
        <nav className="sidebar-nav" aria-label="Project pages">
          <span className="sidebar-section-label">WORKSPACE</span>
          <button
            className={`sidebar-link ${activePage === "documents" ? "active" : ""}`}
            type="button"
            onClick={() => changePage("documents")}
            title="Learner Documents"
          >
            <Files size={18} />
            <span className="sidebar-link-copy">
              <strong>Learner Documents</strong>
              <small>Document matrix</small>
            </span>
          </button>
          <button
            className={`sidebar-link ${activePage === "comparison" ? "active" : ""}`}
            type="button"
            onClick={() => changePage("comparison")}
            title="Start Date Comparison"
          >
            <GitCompareArrows size={18} />
            <span className="sidebar-link-copy">
              <strong>Date Comparison</strong>
              <small>Start date audit</small>
            </span>
          </button>
          <button
            className={`sidebar-link ${activePage === "hours-comparison" ? "active" : ""}`}
            type="button"
            onClick={() => changePage("hours-comparison")}
            title="Planned Hours Comparison"
          >
            <GitCompareArrows size={18} />
            <span className="sidebar-link-copy">
              <strong>Hours Comparison</strong>
              <small>Planned hours audit</small>
            </span>
          </button>
          <button
            className={`sidebar-link ${activePage === "monthly-hours" ? "active" : ""}`}
            type="button"
            onClick={() => changePage("monthly-hours")}
            title="Monthly Learner Hours"
          >
            <Clock3 size={18} />
            <span className="sidebar-link-copy">
              <strong>Monthly Hours</strong>
              <small>Planned and completed</small>
            </span>
          </button>
          <button
            className={`sidebar-link ${activePage === "skills-radar" ? "active" : ""}`}
            type="button"
            onClick={() => changePage("skills-radar")}
            title="Skills Radar Overview"
          >
            <Radar size={18} />
            <span className="sidebar-link-copy">
              <strong>Skills Radar</strong>
              <small>Scores, hours and funding</small>
            </span>
          </button>
          <button
            className={`sidebar-link ${activePage === "funding-comparison" ? "active" : ""}`}
            type="button"
            onClick={() => changePage("funding-comparison")}
            title="Written Agreement Funding"
          >
            <BadgePoundSterling size={18} />
            <span className="sidebar-link-copy">
              <strong>Funding Validation</strong>
              <small>Written Agreement totals</small>
            </span>
          </button>
          <button
            className={`sidebar-link ${activePage === "prior-learning" ? "active" : ""}`}
            type="button"
            onClick={() => changePage("prior-learning")}
            title="Prior Learning Review"
          >
            <FileCheck2 size={18} />
            <span className="sidebar-link-copy">
              <strong>Prior Learning</strong>
              <small>Hours and funding audit</small>
            </span>
          </button>
          <button
            className={`sidebar-link ${activePage === "endpoint-assessment" ? "active" : ""}`}
            type="button"
            onClick={() => changePage("endpoint-assessment")}
            title="Endpoint Assessment Dates"
          >
            <CalendarDays size={18} />
            <span className="sidebar-link-copy">
              <strong>Endpoint Assessment</strong>
              <small>ILR end-date timeline</small>
            </span>
          </button>
        </nav>
        <div className="sidebar-footer">
          <div className="profile">RY</div>
          <div className="sidebar-footer-copy"><strong>Rewan Yasser</strong><span>Administrator</span></div>
        </div>
      </aside>
      {sidebarOpen && <button className="sidebar-overlay" aria-label="Close navigation" onClick={() => setSidebarOpen(false)} />}

      <div className="workspace">
        <header className="topbar">
          <button className="mobile-menu" type="button" onClick={() => setSidebarOpen(true)} aria-label="Open navigation">
            <Menu size={20} />
          </button>
          <div className="topbar-title">
            <span>Workspace</span>
            <strong>{({ documents: "Learner Documents", comparison: "Start Date Comparison", "hours-comparison": "Planned Hours Comparison", "monthly-hours": "Monthly Learner Hours", "skills-radar": "Skills Radar Overview", "funding-comparison": "Funding Validation", "prior-learning": "Prior Learning Review", "endpoint-assessment": "Endpoint Assessment Dates" })[activePage]}</strong>
          </div>
          <div className="topbar-side">
            <span className="db-status"><i /> Database connected</span>
            <div className="profile">RY</div>
          </div>
        </header>

        {activePage === "documents" ? (
        <div className="page">
        <section className="hero">
          <div>
            <span className="eyebrow">DOCUMENT CENTRE</span>
            <h1>Learner Documents</h1>
            <p>Review every learner in one row and manage document links in place.</p>
          </div>
          <button className="primary-button" onClick={() => setCreating(true)}>
            <Plus size={18} /> Add document
          </button>
        </section>

        <section className="summary-grid">
          <SummaryCard icon={Files} label="Total documents" value={summary.documents} detail="All stored records" tone="purple" />
          <SummaryCard icon={UsersRound} label="Learners" value={summary.learners} detail="Unique learners" tone="blue" />
          <SummaryCard icon={Link2} label="Available links" value={summary.linked} detail="Documents with a link" tone="orange" />
          <SummaryCard icon={FileCheck2} label="Completed or signed" value={summary.completed} detail="Ready for review" tone="green" />
        </section>

        <section className="content-card matrix-card">
          <div className="content-heading">
            <div>
              <h2>Learner document matrix</h2>
              <p>{formatNumber(pagination.total)} learners · one learner per row</p>
            </div>
            <button className="refresh-button" onClick={() => loadLearners()} disabled={loading}>
              <RefreshCw size={16} className={loading ? "spin" : ""} /> Refresh
            </button>
          </div>

          <div className="matrix-toolbar">
            <label className="search-box">
              <Search size={18} />
              <input
                value={search}
                onChange={(event) => changeSearch(event.target.value)}
                placeholder="Search by learner, email, programme or document..."
              />
              {search && (
                <button type="button" onClick={() => changeSearch("")} aria-label="Clear search">
                  <X size={16} />
                </button>
              )}
            </label>
            <div className={`learner-scope-filter ${scopeMenuOpen ? "is-open" : ""}`} ref={scopeMenuRef}>
              <button
                className="learner-scope-trigger"
                type="button"
                onClick={() => setScopeMenuOpen((open) => !open)}
                aria-haspopup="listbox"
                aria-expanded={scopeMenuOpen}
              >
                <UserRound size={16} />
                <span>Learners</span>
                <strong>{learnerScope === "ilr" ? "ILR learners" : "All learners"}</strong>
                <ChevronDown size={15} />
              </button>
              {scopeMenuOpen && (
                <div className="learner-scope-menu" role="listbox" aria-label="Filter learners">
                  <button
                    type="button"
                    role="option"
                    aria-selected={learnerScope === "ilr"}
                    className={learnerScope === "ilr" ? "active" : ""}
                    onClick={() => changeLearnerScope("ilr")}
                  >
                    <span><strong>ILR learners</strong><small>Students included in the ILR</small></span>
                    {learnerScope === "ilr" && <Check size={15} />}
                  </button>
                  <button
                    type="button"
                    role="option"
                    aria-selected={learnerScope === "all"}
                    className={learnerScope === "all" ? "active" : ""}
                    onClick={() => changeLearnerScope("all")}
                  >
                    <span><strong>All learners</strong><small>Include learners outside the ILR</small></span>
                    {learnerScope === "all" && <Check size={15} />}
                  </button>
                </div>
              )}
            </div>
            <ProgramStatusFilter value={programStatus} statuses={data?.programStatuses} onChange={changeProgramStatus} />
            <span className="matrix-hint">Scroll horizontally to view every document type</span>
          </div>

          {error ? (
            <div className="state-panel error-state">
              <CircleAlert size={26} />
              <div><strong>Could not load the data</strong><p>{error}</p></div>
              <button onClick={() => loadLearners()}>Try again</button>
            </div>
          ) : (
            <div className={`table-wrap matrix-wrap ${loading ? "is-loading" : ""}`}>
              {loading && <div className="loading-layer"><LoaderCircle size={26} className="spin" /></div>}
              <table className="matrix-table">
                <thead>
                  <tr className="document-group-row">
                    <th className="sticky-learner" rowSpan="2">Learner</th>
                    <th className="sticky-programme" rowSpan="2">Programme</th>
                    <th className="sticky-program-status" rowSpan="2">Program status</th>
                    <th className="sticky-start-date" rowSpan="2">Start date</th>
                    <th className="sticky-end-date" rowSpan="2">End date</th>
                    <th className="sticky-planned-hours" rowSpan="2">Planned hours</th>
                    <th className="sticky-training-plan-hours" rowSpan="2">Training Plan hours</th>
                    <th className="sticky-agreement-hours" rowSpan="2">Agreement hours</th>
                    {documentColumns.map((column) => (
                      <th className="document-group-head" colSpan="2" key={column.key}>{column.label}</th>
                    ))}
                  </tr>
                  <tr className="document-subhead-row">
                    {documentColumns.map((column) => (
                      <Fragment key={column.key}>
                        <th className="document-column-head">Document</th>
                        <th className="updated-to-column-head">Updated to</th>
                      </Fragment>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data?.rows?.map((learner) => (
                    <tr key={learner.learner_id}>
                      <td className="sticky-learner">
                        <div className="person-cell">
                          <span className="avatar">{learner.full_name?.trim()?.[0]?.toUpperCase() || "?"}</span>
                          <div>
                            <strong>{learner.full_name}</strong>
                            <small>{learner.email || `Learner #${learner.learner_id}`}</small>
                          </div>
                        </div>
                      </td>
                      <td className="sticky-programme">
                        <span className="matrix-programme" title={learner.program_name}>{learner.program_name || "—"}</span>
                      </td>
                      <td className="sticky-program-status">
                        <ProgramStatusBadge status={learner.program_status} />
                      </td>
                      <td className="sticky-start-date learner-metric">
                        {learner.learn_start_date ? formatDate(learner.learn_start_date) : "—"}
                      </td>
                      <td className="sticky-end-date learner-metric">
                        {learner.learn_plan_end_date ? formatDate(learner.learn_plan_end_date) : "—"}
                      </td>
                      <td className="sticky-planned-hours learner-metric planned-hours-value">
                        {learner.planned_hours ?? "—"}
                      </td>
                      <td className="sticky-training-plan-hours learner-metric planned-hours-value">
                        {learner.training_plan_planned_hours ?? "—"}
                      </td>
                      <td className="sticky-agreement-hours learner-metric planned-hours-value">
                        {learner.apprenticeship_agreement_planned_hours ?? "—"}
                      </td>
                      {documentColumns.map((column) => (
                        <Fragment key={column.key}>
                          <td className="document-matrix-cell">
                            <DocumentCell
                              documents={learner.documents?.[column.key]}
                              onEdit={(document) => openEdit(document, learner)}
                            />
                          </td>
                          <td className="updated-to-matrix-cell">
                            <UpdatedToCell
                              documents={learner.documents?.[column.key]}
                              onEdit={(document) => openEdit(document, learner)}
                            />
                          </td>
                        </Fragment>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
              {!loading && !data?.rows?.length && (
                <div className="empty-state">
                  <div><Search size={25} /></div>
                  <strong>No learners found</strong>
                  <p>Try a different search term.</p>
                </div>
              )}
            </div>
          )}

          {!error && (
            <div className="pagination">
              <span>Page <b>{pagination.page}</b> of <b>{pagination.pages}</b></span>
              <div>
                <button onClick={() => setPage((current) => Math.max(current - 1, 1))} disabled={page <= 1 || loading}>
                  <ArrowLeft size={17} /> Previous
                </button>
                <button onClick={() => setPage((current) => Math.min(current + 1, pagination.pages))} disabled={page >= pagination.pages || loading}>
                  Next <ArrowRight size={17} />
                </button>
              </div>
            </div>
          )}
        </section>
        </div>
        ) : activePage === "comparison" ? (
          <DateComparisonPage />
        ) : activePage === "hours-comparison" ? (
          <PlannedHoursComparisonPage />
        ) : activePage === "funding-comparison" ? (
          <FundingComparisonPage />
        ) : activePage === "prior-learning" ? (
          <PriorLearningPage />
        ) : activePage === "monthly-hours" ? (
          <MonthlyHoursPage />
        ) : activePage === "skills-radar" ? (
          <SkillsRadarPage />
        ) : (
          <EndpointAssessmentPage />
        )}
      </div>

      {editing && (
        <Modal title="Edit document" subtitle={`${editing.full_name} · ${editing.program_name}`} onClose={() => !saving && setEditing(null)}>
          <form onSubmit={saveEdit}>
            <div className="modal-body">
              <div className="learner-summary">
                <span><UserRound size={18} /></span>
                <div><strong>{editing.full_name}</strong><small>{editing.email || `Learner #${editing.learner_id}`}</small></div>
              </div>
              <Field label="Document name" required>
                <input value={editing.document_name} onChange={(event) => setEditing({ ...editing, document_name: event.target.value })} required />
              </Field>
              <Field label="Document category" required>
                <input value={editing.document_category} onChange={(event) => setEditing({ ...editing, document_category: event.target.value })} required />
              </Field>
              <Field label="Correct file URL" required>
                <div className="url-input">
                  <Link2 size={17} />
                  <input type="url" value={editing.file} onChange={(event) => setEditing({ ...editing, file: event.target.value })} placeholder="https://..." required />
                </div>
                <small className="field-help">Enter the full URL beginning with http:// or https://</small>
              </Field>
              <Field label="Updated to">
                <div className="date-input">
                  <CalendarDays size={17} />
                  <input
                    type="date"
                    value={toDateInput(editing.updated_to)}
                    onChange={(event) => setEditing({ ...editing, updated_to: event.target.value })}
                  />
                </div>
                <small className="field-help">This date is stored separately for this document.</small>
              </Field>
            </div>
            <div className="modal-actions split-actions">
              <button type="button" className="delete-text-button" onClick={() => setDeleting(editing)} disabled={saving}>
                <Trash2 size={16} /> Delete
              </button>
              <div>
                <button type="button" className="secondary-button" onClick={() => setEditing(null)} disabled={saving}>Cancel</button>
                <button type="submit" className="primary-button" disabled={saving}>
                  {saving ? <LoaderCircle size={17} className="spin" /> : <Check size={17} />} Save changes
                </button>
              </div>
            </div>
          </form>
        </Modal>
      )}

      {creating && (
        <Modal title="Add a new document" subtitle="Enter the learner and document details." onClose={() => !saving && setCreating(false)} wide>
          <form onSubmit={createDocument}>
            <div className="modal-body form-grid">
              <Field label="Learner ID" required>
                <input type="number" min="1" value={createForm.learnerId} onChange={(event) => setCreateForm({ ...createForm, learnerId: event.target.value })} required />
              </Field>
              <Field label="Learner name" required>
                <input value={createForm.fullName} onChange={(event) => setCreateForm({ ...createForm, fullName: event.target.value })} required />
              </Field>
              <Field label="Email">
                <input type="email" value={createForm.email} onChange={(event) => setCreateForm({ ...createForm, email: event.target.value })} />
              </Field>
              <Field label="Programme" required>
                <input value={createForm.programName} onChange={(event) => setCreateForm({ ...createForm, programName: event.target.value })} required />
              </Field>
              <Field label="Document name" required>
                <input value={createForm.documentName} onChange={(event) => setCreateForm({ ...createForm, documentName: event.target.value })} required />
              </Field>
              <Field label="Category" required>
                <select value={createForm.category} onChange={(event) => setCreateForm({ ...createForm, category: event.target.value })}>
                  <option value="CONTRACT">CONTRACT</option>
                  <option value="CV">CV</option>
                  <option value="CV_TEXT">CV_TEXT</option>
                </select>
              </Field>
              <Field label="File URL" required className="full-field">
                <div className="url-input">
                  <Link2 size={17} />
                  <input type="url" value={createForm.file} onChange={(event) => setCreateForm({ ...createForm, file: event.target.value })} placeholder="https://..." required />
                </div>
              </Field>
              <Field label="Updated to" className="full-field">
                <div className="date-input">
                  <CalendarDays size={17} />
                  <input type="date" value={createForm.updatedTo} onChange={(event) => setCreateForm({ ...createForm, updatedTo: event.target.value })} />
                </div>
              </Field>
            </div>
            <div className="modal-actions">
              <button type="button" className="secondary-button" onClick={() => setCreating(false)} disabled={saving}>Cancel</button>
              <button type="submit" className="primary-button" disabled={saving}>
                {saving ? <LoaderCircle size={17} className="spin" /> : <FilePlus2 size={17} />} Add document
              </button>
            </div>
          </form>
        </Modal>
      )}

      {deleting && (
        <Modal title="Delete document?" subtitle="This will permanently remove the database record." onClose={() => !saving && setDeleting(null)}>
          <div className="delete-confirm">
            <div className="delete-icon"><Trash2 size={23} /></div>
            <div><strong>{deleting.document_name}</strong><p>{deleting.full_name}</p></div>
          </div>
          <div className="modal-actions">
            <button className="secondary-button" onClick={() => setDeleting(null)} disabled={saving}>Cancel</button>
            <button className="danger-button" onClick={deleteDocument} disabled={saving}>
              {saving ? <LoaderCircle size={17} className="spin" /> : <Trash2 size={17} />} Delete document
            </button>
          </div>
        </Modal>
      )}

      {toast && (
        <div className={`toast ${toast.tone}`}>
          {toast.tone === "success" ? <Check size={18} /> : <CircleAlert size={18} />}
          <span>{toast.message}</span>
          <button onClick={() => setToast(null)}><X size={15} /></button>
        </div>
      )}
    </main>
  );
}
