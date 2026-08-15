import { useRun } from '../context/useRun';
import '../styles/shared.css';
import './ReportsPage.css';

const VERDICT_COPY = {
  approved: 'Final cut — approved',
  rejected: 'Cut — rejected',
  pending: 'Rough cut — pending review',
  flagged: 'Rough cut — pending review',
};

function formatDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString();
}

function downloadRun(run) {
  const blob = new Blob([JSON.stringify(run, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `${run.script_id}-clearance-report.json`;
  link.click();
  URL.revokeObjectURL(url);
}

export default function ReportsPage() {
  const { run } = useRun();

  const counts = run.entities.reduce(
    (acc, e) => {
      acc[e.status] = (acc[e.status] ?? 0) + 1;
      return acc;
    },
    { flagged: 0, cleared: 0, overridden: 0 }
  );

  return (
    <div className="app-page">
      <span className="page-eyebrow">STEP 5 · REPORT</span>
      <h1 className="page-title">Insurance-ready report</h1>
      <p className="page-sub">
        A structured summary of this clearance run, ready to hand to E&amp;O
        insurers or legal teams.
      </p>

      <span className={`verdict-slate verdict-slate--${run.overall_status}`}>
        {VERDICT_COPY[run.overall_status] ?? VERDICT_COPY.pending}
      </span>

      <div className="run-header panel">
        <div>
          <h2 className="run-header-title">{run.script_title}</h2>
          <span className="run-header-sub">Run ID: {run.run_id}</span>
        </div>
        <span className={`status-pill status-pill--${run.overall_status}`}>
          {run.overall_status}
        </span>
      </div>

      <div className="report-counts">
        <div className="report-count-tile">
          <span className="report-count-value">{counts.cleared}</span>
          <span className="report-count-label">Cleared</span>
        </div>
        <div className="report-count-tile">
          <span className="report-count-value">{counts.flagged}</span>
          <span className="report-count-label">Flagged</span>
        </div>
        <div className="report-count-tile">
          <span className="report-count-value">{counts.overridden}</span>
          <span className="report-count-label">Overridden</span>
        </div>
        <div className="report-count-tile">
          <span className="report-count-value">{run.metadata.total_pages_scanned}</span>
          <span className="report-count-label">Pages scanned</span>
        </div>
      </div>

      <div className="panel filmstrip-frame report-detail">
        <dl className="credits-list">
          <div className="credits-row">
            <dt>Reviewed by</dt>
            <span className="credits-leader" aria-hidden="true" />
            <dd>{run.reviewed_by ?? 'Not yet reviewed'}</dd>
          </div>
          <div className="credits-row">
            <dt>Reviewed at</dt>
            <span className="credits-leader" aria-hidden="true" />
            <dd>{formatDate(run.reviewed_at)}</dd>
          </div>
          <div className="credits-row">
            <dt>Created</dt>
            <span className="credits-leader" aria-hidden="true" />
            <dd>{formatDate(run.created_at)}</dd>
          </div>
          <div className="credits-row">
            <dt>Extraction model</dt>
            <span className="credits-leader" aria-hidden="true" />
            <dd>{run.metadata.model_used}</dd>
          </div>
        </dl>
      </div>

      <button className="btn-primary report-download" onClick={() => downloadRun(run)}>
        Download report (JSON)
      </button>
    </div>
  );
}
