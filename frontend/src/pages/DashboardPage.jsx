import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  listClearanceRuns,
  downloadClearancePdf,
  openClearancePdfPreview,
} from '../api/clearanceClient';
import PdfPreviewModal from '../components/PdfPreviewModal';
import { useAuth } from '../auth/AuthContext';
import { useRun } from '../context/useRun';
import { allEntitiesReviewed } from '../context/steps';
import './DashboardPage.css';

const FILTERS = [
  { id: 'all', label: 'All' },
  { id: 'awaiting', label: 'Awaiting review' },
  { id: 'cleared', label: 'Cleared' },
  { id: 'blocked', label: 'Blocked' },
  { id: 'processing', label: 'Processing' },
];

function greetingForNow(date = new Date()) {
  const hour = date.getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 18) return 'Good afternoon';
  return 'Good evening';
}

function formatShortDate(iso) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      month: 'short',
      day: '2-digit',
    });
  } catch {
    return iso;
  }
}

function titleOf(row) {
  return row.script_title?.trim() || 'Untitled screenplay';
}

function deskStatus(row) {
  if (row.cleared_for_export || row.overall_status === 'approved') {
    return { id: 'cleared', label: 'Cleared' };
  }
  if (row.overall_status === 'rejected') {
    return { id: 'blocked', label: 'Blocked' };
  }
  if (row.overall_status === 'pending' && !row.entity_count) {
    return { id: 'processing', label: 'Processing' };
  }
  return { id: 'awaiting', label: 'Awaiting review' };
}

function matchesFilter(row, filterId) {
  if (filterId === 'all') return true;
  return deskStatus(row).id === filterId;
}

function riskCounts(row) {
  return {
    high: Number(row.high_count) || 0,
    caution: Number(row.caution_count) || 0,
    clear: Number(row.clear_count) || 0,
  };
}

function RiskSpread({ row }) {
  const { high, caution, clear } = riskCounts(row);
  const total = high + caution + clear || 1;
  return (
    <div className="desk-risk">
      <div className="desk-risk-bar" aria-hidden="true">
        <span style={{ width: `${(high / total) * 100}%` }} className="is-high" />
        <span style={{ width: `${(caution / total) * 100}%` }} className="is-caution" />
        <span style={{ width: `${(clear / total) * 100}%` }} className="is-clear" />
      </div>
      <div className="desk-risk-legend">
        <span>{high} high</span>
        <span>{caution} caution</span>
        <span>{clear} clear</span>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { reloadRun } = useRun();
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [openingId, setOpeningId] = useState(null);
  const [downloadingId, setDownloadingId] = useState(null);
  const [filter, setFilter] = useState('all');
  // preview holds the in-flight or active PDF preview. `url` is a blob: URL that
  // must be revoked when the modal closes or the component unmounts.
  const [preview, setPreview] = useState(null);
  const [viewingId, setViewingId] = useState(null);

  useEffect(() => {
    // Wait until Firebase has a signed-in user before listing; otherwise the
    // request goes out without a Bearer token and the desk looks empty/broken.
    if (!user?.uid) {
      setLoading(true);
      setRuns([]);
      setError(null);
      return undefined;
    }

    const controller = new AbortController();
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const rows = await listClearanceRuns({ signal: controller.signal });
        setRuns(rows);
      } catch (err) {
        if (err?.name === 'AbortError') return;
        setError(err instanceof Error ? err.message : 'Could not load reports.');
      } finally {
        setLoading(false);
      }
    })();
    return () => controller.abort();
  }, [user?.uid]);

  const stats = useMemo(() => {
    const scripts = runs.length;
    const totalFlags = runs.reduce((sum, row) => sum + (Number(row.entity_count) || 0), 0);
    const awaiting = runs.filter((row) => deskStatus(row).id === 'awaiting').length;
    const highUnresolved = runs.reduce((sum, row) => {
      if (deskStatus(row).id === 'cleared') return sum;
      return sum + (Number(row.high_count) || 0);
    }, 0);
    const cleared = runs.filter((row) => deskStatus(row).id === 'cleared').length;
    const clearanceRate = scripts ? Math.round((cleared / scripts) * 100) : 0;
    return { scripts, totalFlags, awaiting, highUnresolved, clearanceRate };
  }, [runs]);

  const attention = useMemo(() => {
    return runs
      .filter((row) => {
        const id = deskStatus(row).id;
        return id === 'awaiting' || id === 'blocked';
      })
      .slice(0, 2);
  }, [runs]);

  const filtered = useMemo(
    () => runs.filter((row) => matchesFilter(row, filter)),
    [runs, filter]
  );

  async function openRun(runId) {
    setOpeningId(runId);
    setError(null);
    try {
      const response = await reloadRun(runId);
      const run = response?.run;
      if (!run) {
        throw new Error('Could not open this report.');
      }
      navigate(allEntitiesReviewed(run) ? '/reports' : '/review');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not open this report.');
      setOpeningId(null);
    }
  }

  async function viewPdf(runId, scriptTitle) {
    setViewingId(runId);
    setError(null);
    // Show the modal immediately in a loading state so the click feels responsive.
    setPreview({
      runId,
      title: scriptTitle,
      url: null,
      loading: true,
      error: null,
      reportHash: null,
      reportSource: null,
    });
    try {
      const { url, reportHash, reportSource } = await openClearancePdfPreview(runId);
      setPreview({
        runId,
        title: scriptTitle,
        url,
        loading: false,
        error: null,
        reportHash,
        reportSource,
      });
    } catch (err) {
      setPreview({
        runId,
        title: scriptTitle,
        url: null,
        loading: false,
        error: err instanceof Error ? err.message : 'Could not open this report.',
        reportHash: null,
        reportSource: null,
      });
    } finally {
      setViewingId(null);
    }
  }

  function closePreview() {
    setPreview(null);
  }

  // Single owner of blob lifetime: revokes the previous URL whenever it changes
  // and on unmount, so closing the modal or leaving the page frees the bytes.
  useEffect(() => {
    const activeUrl = preview?.url;
    if (!activeUrl) return undefined;
    return () => URL.revokeObjectURL(activeUrl);
  }, [preview?.url]);

  async function downloadPdf(runId, scriptTitle) {
    setDownloadingId(runId);
    setError(null);
    try {
      const safe = String(scriptTitle || 'screenplay')
        .replace(/\.(pdf|txt)$/i, '')
        .replace(/[^\w.\-]+/g, '_')
        .replace(/_+/g, '_')
        .replace(/^_|_$/g, '');
      await downloadClearancePdf(runId, {
        filename: `${safe || 'screenplay'}_scriptclearAI.pdf`,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not download PDF.');
    } finally {
      setDownloadingId(null);
    }
  }

  const firstName = user?.displayName?.split(/\s+/)[0] || null;

  return (
    <div className="app-page dashboard-page">
      <header className="desk-hero">
        <p className="desk-greeting">
          {firstName ? `${greetingForNow()}, ${firstName}.` : `${greetingForNow()}.`}
        </p>
        <h1 className="desk-title">The cutting room</h1>
        <p className="desk-sub">
          {loading
            ? 'Loading your clearance desk…'
            : stats.awaiting || stats.highUnresolved
              ? `${stats.awaiting} script${stats.awaiting === 1 ? '' : 's'} waiting on your sign-off · ${stats.highUnresolved} high-exposure mark${stats.highUnresolved === 1 ? '' : 's'} unresolved.`
              : runs.length
                ? 'All current scripts are clear of pending sign-off.'
                : 'No clearance runs yet — start with a new screenplay.'}
        </p>
      </header>

      <section className="desk-stats" aria-label="Clearance summary">
        <div className="desk-stat">
          <strong>{stats.scripts}</strong>
          <span>Scripts analysed</span>
        </div>
        <div className="desk-stat">
          <strong>{stats.totalFlags}</strong>
          <span>Total flags</span>
        </div>
        <div className={`desk-stat${stats.awaiting ? ' is-accent' : ''}`}>
          <strong>{stats.awaiting}</strong>
          <span>Awaiting you</span>
        </div>
        <div className={`desk-stat${stats.highUnresolved ? ' is-danger' : ''}`}>
          <strong>{stats.highUnresolved}</strong>
          <span>High unresolved</span>
        </div>
        <div className="desk-stat">
          <strong>{stats.clearanceRate}%</strong>
          <span>Clearance rate</span>
        </div>
      </section>

      {error ? <p className="dashboard-error">{error}</p> : null}

      {!loading && attention.length > 0 ? (
        <section className="desk-attention">
          <div className="desk-section-label">
            <span className="desk-flag" aria-hidden="true" />
            Needs your attention
          </div>
          <div className="desk-attention-grid">
            {attention.map((row) => {
              const status = deskStatus(row);
              const high = Number(row.high_count) || 0;
              const detail =
                status.id === 'blocked'
                  ? `Export blocked — ${high || row.entity_count || 0} unresolved.`
                  : `${high || row.entity_count || 0} high-exposure mark${(high || row.entity_count) === 1 ? '' : 's'} awaiting sign-off.`;
              return (
                <button
                  key={row.run_id}
                  type="button"
                  className="desk-attention-card"
                  disabled={openingId === row.run_id}
                  onClick={() => openRun(row.run_id)}
                >
                  <div className="desk-attention-copy">
                    <h2>{titleOf(row)}</h2>
                    <p>{detail}</p>
                  </div>
                  <span className={`desk-pill status-${status.id}`}>
                    {openingId === row.run_id ? 'Opening…' : status.label}
                  </span>
                </button>
              );
            })}
          </div>
        </section>
      ) : null}

      <section className="desk-reels">
        <div className="desk-reels-head">
          <h2 className="desk-section-title">Your reels</h2>
          <div className="desk-filters" role="tablist" aria-label="Filter reports">
            {FILTERS.map((item) => (
              <button
                key={item.id}
                type="button"
                role="tab"
                aria-selected={filter === item.id}
                className={`desk-filter${filter === item.id ? ' is-active' : ''}`}
                onClick={() => setFilter(item.id)}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>

        {loading ? (
          <p className="dashboard-empty">Loading your reports…</p>
        ) : runs.length === 0 ? (
          <div className="dashboard-empty-panel panel">
            <h2>No reports for this account</h2>
            <p>
              Clearance history is tied to the Google account you signed in with.
              Local <code>dev-user</code> test runs will not appear here. Upload a
              screenplay to create the first report for this account.
            </p>
            <Link className="btn-primary" to="/upload">
              Start clearance
            </Link>
          </div>
        ) : filtered.length === 0 ? (
          <p className="dashboard-empty">No reels match this filter.</p>
        ) : (
          <div className="desk-table-wrap">
            <table className="desk-table">
              <thead>
                <tr>
                  <th>Production</th>
                  <th>Date</th>
                  <th>Entities</th>
                  <th>Risk spread</th>
                  <th>Status</th>
                  <th>Report</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((row) => {
                  const status = deskStatus(row);
                  return (
                    <tr key={row.run_id}>
                      <td>
                        <button
                          type="button"
                          className="desk-prod-link"
                          disabled={openingId === row.run_id}
                          onClick={() => openRun(row.run_id)}
                        >
                          {titleOf(row)}
                        </button>
                      </td>
                      <td>{formatShortDate(row.updated_at || row.created_at)}</td>
                      <td>{row.entity_count ?? 0}</td>
                      <td>
                        <RiskSpread row={row} />
                      </td>
                      <td>
                        <button
                          type="button"
                          className={`desk-pill status-${status.id}`}
                          disabled={openingId === row.run_id}
                          onClick={() => openRun(row.run_id)}
                        >
                          {openingId === row.run_id ? 'Opening…' : status.label}
                        </button>
                      </td>
                      <td>
                        <div className="desk-report-actions">
                          <button
                            type="button"
                            className="desk-download"
                            disabled={viewingId === row.run_id}
                            onClick={() => viewPdf(row.run_id, titleOf(row))}
                          >
                            {viewingId === row.run_id ? 'Opening…' : 'View'}
                          </button>
                          <button
                            type="button"
                            className="desk-download"
                            disabled={downloadingId === row.run_id}
                            onClick={() => downloadPdf(row.run_id, titleOf(row))}
                          >
                            {downloadingId === row.run_id ? 'Saving…' : 'Download'}
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <div className="desk-cta">
        <Link className="desk-cta-btn" to="/upload">
          + New clearance run
        </Link>
      </div>

      {preview ? (
        <PdfPreviewModal
          title={preview.title}
          url={preview.url}
          loading={preview.loading}
          error={preview.error}
          reportHash={preview.reportHash}
          reportSource={preview.reportSource}
          onClose={closePreview}
          onDownload={
            preview.url ? () => downloadPdf(preview.runId, preview.title) : undefined
          }
        />
      ) : null}
    </div>
  );
}
