import { useEffect, useMemo, useRef, useState } from 'react';
import { useRun } from '../context/useRun';
import { downloadClearancePdf } from '../api/clearanceClient';
import { isSafeHttpUrl } from '../api/safeUrl';
import ReportVerifier from '../components/ReportVerifier';
import '../styles/shared.css';
import './ReportsPage.css';

const TYPE_LABELS = {
  business: 'Business',
  character_name: 'Character name',
  song: 'Song',
  logo_brand: 'Logo / Brand',
  address: 'Address',
  phone_number: 'Phone number',
  license_plate: 'License plate',
  quote_or_literary_reference: 'Literary reference',
  real_public_figure: 'Real public figure',
};

const VERDICT_COPY = {
  approved: {
    label: 'APPROVED FOR CLEARANCE',
    detail: 'Human legal review completed. This run is marked approved.',
  },
  rejected: {
    label: 'RUN REJECTED',
    detail: 'This clearance run was blocked by legal review.',
  },
  pending: {
    label: 'PENDING FINAL APPROVAL',
    detail: 'Entity decisions recorded; overall run approval not yet set.',
  },
  flagged: {
    label: 'PENDING FINAL APPROVAL',
    detail: 'Gatekeeper has not cleared this run for export.',
  },
};

const DECISION_LABELS = {
  cleared: 'Approved',
  blocked: 'Blocked',
  overridden: 'Dismissed',
  flagged: 'Still flagged',
};

function formatDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString();
}

/** Build export basename: Screenplay_1_scriptclearAI */
function reportExportBaseName(run) {
  const raw =
    run.metadata?.source_file_name ||
    run.script_title ||
    run.script_id ||
    'screenplay';
  const base = String(raw)
    .replace(/\.(pdf|txt)$/i, '')
    .replace(/[^\w.\-]+/g, '_')
    .replace(/_+/g, '_')
    .replace(/^_|_$/g, '');
  return `${base || 'screenplay'}_scriptclearAI`;
}

function pageLabel(entity) {
  const page = entity.location?.page_number;
  return page ? `Page ${page}` : 'Page —';
}

function buildWarnings(run, lastResponse) {
  const warnings = [];
  const stillFlagged = run.entities.filter((e) => e.status === 'flagged');
  const blocked = run.entities.filter((e) => e.status === 'blocked');
  const unresolvedHighRisk = run.entities.filter(
    (e) => e.requires_human_review && e.status === 'flagged'
  );
  const researchGaps = run.entities.filter(
    (e) =>
      !e.research_finding ||
      (typeof e.research_finding === 'string' &&
        /unavailable|high demand|503|tool_failure|not available/i.test(
          e.research_finding
        ))
  );

  if (unresolvedHighRisk.length) {
    warnings.push(
      `${unresolvedHighRisk.length} high-risk entit${unresolvedHighRisk.length === 1 ? 'y remains' : 'ies remain'} unresolved — do not treat this run as fully cleared.`
    );
  }
  if (stillFlagged.length) {
    warnings.push(
      `${stillFlagged.length} entit${stillFlagged.length === 1 ? 'y is' : 'ies are'} still flagged with no human decision.`
    );
  }
  if (blocked.length) {
    warnings.push(
      `${blocked.length} entit${blocked.length === 1 ? 'y was' : 'ies were'} blocked by legal review and must not be used as-is.`
    );
  }
  if (lastResponse && lastResponse.cleared_for_export === false) {
    warnings.push(
      'This run is not cleared for export. Confirm human decisions before sharing externally.'
    );
  }
  if (researchGaps.length) {
    warnings.push(
      `${researchGaps.length} entit${researchGaps.length === 1 ? 'y has' : 'ies have'} incomplete or unavailable specialist research — treat AI findings as provisional.`
    );
  }
  if (!warnings.length) {
    warnings.push(
      'No critical warnings. AI-assisted research still requires professional legal judgment.'
    );
  }
  return warnings;
}

function downloadFullReport(payload, fileBase) {
  const blob = new Blob([JSON.stringify(payload, null, 2)], {
    type: 'application/json',
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `${fileBase}.json`;
  link.click();
  URL.revokeObjectURL(url);
}

function DecisionTable({ title, tone, entities }) {
  if (!entities.length) {
    return (
      <section className={`report-decision report-decision--${tone}`}>
        <h3>{title}</h3>
        <p className="report-empty">None</p>
      </section>
    );
  }

  return (
    <section className={`report-decision report-decision--${tone}`}>
      <h3>
        {title} <span>({entities.length})</span>
      </h3>
      <div className="report-table-wrap">
        <table className="report-table">
          <thead>
            <tr>
              <th>Entity</th>
              <th>Type</th>
              <th>Location</th>
              <th>AI risk</th>
              <th>Decision</th>
            </tr>
          </thead>
          <tbody>
            {entities.map((entity) => (
              <tr key={entity.entity_id}>
                <td>
                  <strong>{entity.name}</strong>
                </td>
                <td>{TYPE_LABELS[entity.entity_type] ?? entity.entity_type}</td>
                <td>{pageLabel(entity)}</td>
                <td>{entity.risk_level ?? '—'}</td>
                <td>{DECISION_LABELS[entity.status] ?? entity.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default function ReportsPage() {
  const { run, lastResponse, reloadRun } = useRun();
  const reportRef = useRef(null);
  const [pdfBusy, setPdfBusy] = useState(false);
  const [pdfError, setPdfError] = useState('');

  useEffect(() => {
    if (run.run_id) {
      reloadRun(run.run_id).catch(() => {});
    }
  }, [run.run_id, reloadRun]);

  const grouped = useMemo(() => {
    const buckets = {
      cleared: [],
      blocked: [],
      overridden: [],
      flagged: [],
    };
    for (const entity of run.entities) {
      const key = buckets[entity.status] ? entity.status : 'flagged';
      buckets[key].push(entity);
    }
    return buckets;
  }, [run.entities]);

  const warnings = useMemo(
    () => buildWarnings(run, lastResponse),
    [run, lastResponse]
  );

  const exportBase = useMemo(() => reportExportBaseName(run), [run]);

  const verdict =
    VERDICT_COPY[run.overall_status] ?? VERDICT_COPY.pending;
  const summary = lastResponse?.summary;
  const gatekeeper = lastResponse?.gatekeeper;
  const recommendations = lastResponse?.recommendations ?? [];
  const clearedForExport = lastResponse?.cleared_for_export === true;

  function handlePrint() {
    const previousTitle = document.title;
    document.title = exportBase;
    document.body.classList.add('is-printing');

    const restore = () => {
      document.title = previousTitle;
      document.body.classList.remove('is-printing');
      window.removeEventListener('afterprint', restore);
    };

    window.addEventListener('afterprint', restore);

    // Let the print class apply before the dialog opens (avoids blank sheets
    // in Chromium when fixed overlays / isolation are still painted).
    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(() => {
        try {
          window.print();
        } catch {
          restore();
        }
        // Fallback if afterprint never fires (some WebViews).
        window.setTimeout(restore, 2000);
      });
    });
  }

  function handleDownloadJson() {
    downloadFullReport(
      {
        generated_at: new Date().toISOString(),
        product: 'ScriptClear AI',
        document_type: 'E&O Clearance Report',
        export_name: exportBase,
        script_title: run.script_title || null,
        overall_status: run.overall_status,
        cleared_for_export: clearedForExport,
        reviewed_by: run.reviewed_by,
        reviewed_at: run.reviewed_at,
        summary,
        gatekeeper: gatekeeper
          ? {
              status: gatekeeper.status,
              reason: gatekeeper.reason,
              message: gatekeeper.message,
              cleared_for_export: gatekeeper.cleared_for_export,
            }
          : null,
        recommendations,
        entities: run.entities.map((entity) => ({
          name: entity.name,
          entity_type: entity.entity_type,
          location: entity.location,
          risk_level: entity.risk_level,
          status: entity.status,
          research_finding: entity.research_finding,
          evidence: (entity.evidence || []).filter(
            (ev) => !ev.source_url || isSafeHttpUrl(ev.source_url)
          ),
        })),
        decision_ledger: {
          approved: grouped.cleared.map((e) => e.name),
          blocked: grouped.blocked.map((e) => e.name),
          dismissed: grouped.overridden.map((e) => e.name),
          still_flagged: grouped.flagged.map((e) => e.name),
        },
        warnings,
      },
      exportBase
    );
  }

  async function handleDownloadPdf() {
    if (!run.run_id) return;
    setPdfBusy(true);
    setPdfError('');
    try {
      await downloadClearancePdf(run.run_id, {
        filename: `${exportBase}.pdf`,
      });
    } catch (err) {
      setPdfError(err instanceof Error ? err.message : 'Could not download PDF.');
    } finally {
      setPdfBusy(false);
    }
  }

  return (
    <div className="app-page reports-page">
      <span className="page-eyebrow">STEP 5 · REPORT</span>
      <h1 className="page-title">Clearance report</h1>
      <p className="page-sub">
        Branded clearance summary with AI findings, human decisions,
        warnings, and gatekeeper status — ready to print or export.
      </p>

      <div className="report-toolbar no-print">
        <button type="button" className="btn-primary" onClick={handlePrint}>
          Print / Save as PDF
        </button>
        <button
          type="button"
          className="btn-ghost"
          onClick={handleDownloadPdf}
          disabled={!run.run_id || pdfBusy}
        >
          {pdfBusy ? 'Downloading…' : 'Download PDF'}
        </button>
        <button type="button" className="btn-ghost" onClick={handleDownloadJson}>
          Download report JSON
        </button>
        <span className="report-export-hint">
          Export name: <code>{exportBase}</code>
        </span>
      </div>
      {pdfError ? <p className="report-pdf-error no-print">{pdfError}</p> : null}

      <ReportVerifier
        expectedHash={run.report_hash}
        signedOffAt={run.reviewed_at}
      />

      <article ref={reportRef} className="clearance-report panel">
        <header className="report-cover">
          <div className="report-brand">
            ScriptClear <span>AI</span>
          </div>
          <p className="report-confidential">
            CONFIDENTIAL — E&amp;O CLEARANCE REPORT
          </p>
          <h2 className="report-script-title">
            {run.script_title || 'Untitled Screenplay'}
          </h2>
          <div className="report-cover-meta">
            <span>Generated: {formatDate(new Date().toISOString())}</span>
            <span>
              Export eligibility:{' '}
              {clearedForExport ? 'Cleared for export' : 'Not cleared for export'}
            </span>
          </div>
        </header>

        <div className={`report-verdict report-verdict--${run.overall_status}`}>
          <strong>{verdict.label}</strong>
          <span>{verdict.detail}</span>
        </div>

        <section className="report-section report-warnings">
          <h3>Warnings</h3>
          <ul>
            {warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </section>

        <section className="report-section">
          <h3>Run metadata</h3>
          <dl className="report-meta-grid">
            <div>
              <dt>Reviewed by</dt>
              <dd>{run.reviewed_by ?? 'Not yet reviewed'}</dd>
            </div>
            <div>
              <dt>Reviewed at</dt>
              <dd>{formatDate(run.reviewed_at)}</dd>
            </div>
            <div>
              <dt>Pipeline started</dt>
              <dd>{formatDate(run.created_at)}</dd>
            </div>
            <div>
              <dt>Pages scanned</dt>
              <dd>{run.metadata?.total_pages_scanned ?? '—'}</dd>
            </div>
            <div>
              <dt>Entities</dt>
              <dd>{run.entities.length}</dd>
            </div>
            <div>
              <dt>Cleared for export</dt>
              <dd>{clearedForExport ? 'Yes' : 'No'}</dd>
            </div>
          </dl>
        </section>

        {summary && (
          <section className="report-section">
            <h3>Executive summary</h3>
            <p className="report-summary-text">{summary.overall_summary}</p>
            <div className="report-summary-stats">
              <span>Clear: {summary.clear_count ?? 0}</span>
              <span>Caution: {summary.caution_count ?? 0}</span>
              <span>High risk: {summary.high_risk_count ?? 0}</span>
              <span>Total: {summary.total_entities ?? run.entities.length}</span>
            </div>
            {Array.isArray(summary.priority_items) &&
              summary.priority_items.length > 0 && (
                <>
                  <h4 className="report-subhead">Priority items</h4>
                  <ul className="report-bullets">
                    {summary.priority_items.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </>
              )}
          </section>
        )}

        {gatekeeper && (
          <section className="report-section">
            <h3>Gatekeeper</h3>
            <dl className="report-meta-grid">
              <div>
                <dt>Status</dt>
                <dd>{gatekeeper.status}</dd>
              </div>
              <div>
                <dt>Reason</dt>
                <dd>{gatekeeper.reason}</dd>
              </div>
              <div>
                <dt>Cleared for export</dt>
                <dd>{gatekeeper.cleared_for_export ? 'Yes' : 'No'}</dd>
              </div>
            </dl>
            {gatekeeper.message && (
              <p className="report-summary-text">{gatekeeper.message}</p>
            )}
          </section>
        )}

        <section className="report-section">
          <h3>Human decision ledger</h3>
          <div className="report-counts report-counts--ledger">
            <div className="report-count-tile report-count-tile--cleared">
              <span className="report-count-value">{grouped.cleared.length}</span>
              <span className="report-count-label">Approved</span>
            </div>
            <div className="report-count-tile report-count-tile--blocked">
              <span className="report-count-value">{grouped.blocked.length}</span>
              <span className="report-count-label">Blocked</span>
            </div>
            <div className="report-count-tile report-count-tile--overridden">
              <span className="report-count-value">
                {grouped.overridden.length}
              </span>
              <span className="report-count-label">Dismissed</span>
            </div>
            <div className="report-count-tile report-count-tile--flagged">
              <span className="report-count-value">{grouped.flagged.length}</span>
              <span className="report-count-label">Still flagged</span>
            </div>
          </div>

          <DecisionTable
            title="Approved by legal"
            tone="cleared"
            entities={grouped.cleared}
          />
          <DecisionTable
            title="Blocked by legal"
            tone="blocked"
            entities={grouped.blocked}
          />
          <DecisionTable
            title="Dismissed / overridden"
            tone="overridden"
            entities={grouped.overridden}
          />
          <DecisionTable
            title="Still flagged — unresolved"
            tone="flagged"
            entities={grouped.flagged}
          />
        </section>

        {recommendations.length > 0 && (
          <section className="report-section">
            <h3>Recommendations</h3>
            <ul className="report-bullets">
              {recommendations.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </section>
        )}

        <section className="report-section">
          <h3>Entity appendix</h3>
          <div className="report-appendix">
            {run.entities.map((entity, index) => (
              <div key={entity.entity_id} className="report-appendix-item">
                <div className="report-appendix-head">
                  <span className="report-appendix-index">
                    {String(index + 1).padStart(2, '0')}
                  </span>
                  <div>
                    <strong>{entity.name}</strong>
                    <p>
                      {TYPE_LABELS[entity.entity_type] ?? entity.entity_type}
                      {' · '}
                      {pageLabel(entity)}
                      {' · '}
                      {DECISION_LABELS[entity.status] ?? entity.status}
                      {entity.requires_human_review
                        ? ' · Required human review'
                        : ''}
                    </p>
                  </div>
                </div>
                {entity.location?.line_excerpt && (
                  <blockquote>“{entity.location.line_excerpt}”</blockquote>
                )}
                {entity.research_finding && (
                  <p className="report-appendix-finding">
                    <span>Research:</span> {entity.research_finding}
                  </p>
                )}
                {Array.isArray(entity.evidence) && entity.evidence.length > 0 && (
                  <ul className="report-evidence">
                    {entity.evidence.map((ev, i) => (
                      <li key={`${entity.entity_id}-ev-${i}`}>
                        {isSafeHttpUrl(ev.source_url) ? (
                          <a
                            href={ev.source_url}
                            target="_blank"
                            rel="noopener noreferrer"
                          >
                            {ev.source_url}
                          </a>
                        ) : (
                          ev.summary || 'Evidence item'
                        )}
                        {ev.summary && isSafeHttpUrl(ev.source_url)
                          ? ` — ${ev.summary}`
                          : ''}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        </section>

        <footer className="report-disclaimer">
          <p>
            This document was generated by <strong>ScriptClear AI</strong>, an
            AI-assisted screenplay E&amp;O clearance system. Findings and
            research are provisional. Human legal review is required before
            production, distribution, or insurance submission. This report is
            not legal advice.
          </p>
        </footer>
      </article>
    </div>
  );
}
