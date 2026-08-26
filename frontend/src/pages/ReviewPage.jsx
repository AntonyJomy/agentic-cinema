import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useRun } from '../context/useRun';
import EntityCard from '../components/EntityCard';
import { allEntitiesReviewed } from '../context/steps';
import '../styles/shared.css';
import './ReviewPage.css';

const DECISION_TO_API = {
  cleared: 'approved',
  blocked: 'blocked',
  overridden: 'approved',
};

export default function ReviewPage() {
  const {
    run,
    lastResponse,
    submitEntityDecision,
    reloadRun,
    error,
    isLoading,
  } = useRun();
  const navigate = useNavigate();
  const [busyId, setBusyId] = useState(null);

  useEffect(() => {
    if (run.run_id) {
      reloadRun(run.run_id).catch(() => {});
    }
  }, [run.run_id, reloadRun]);

  const highRisk = run.entities.filter((e) => e.requires_human_review);
  const highRiskResolved = highRisk.filter((e) => e.status !== 'flagged');
  const gateClear = highRisk.length === 0 || highRiskResolved.length === highRisk.length;
  const reviewedCount = run.entities.filter((e) => e.status !== 'flagged').length;
  const allReviewed = allEntitiesReviewed(run);
  const clearedForExport = lastResponse?.cleared_for_export === true;

  async function handleEntityDecision(entityId, uiStatus) {
    const decision = DECISION_TO_API[uiStatus];
    if (!decision) return;
    setBusyId(entityId);
    try {
      await submitEntityDecision(
        entityId,
        decision,
        uiStatus === 'overridden' ? 'dismissed' : undefined
      );
    } catch {
      // error is stored on context
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="app-page">
      <span className="page-eyebrow">STEP 4 · LEGAL REVIEW</span>
      <h1 className="page-title">Review &amp; decide</h1>
      <p className="page-sub">
        Approve, block, or dismiss each flagged entity. Decisions are stored on
        the server. Export eligibility is calculated by the gatekeeper from those
        entity decisions.
      </p>

      <div className={'gatekeeper-banner' + (gateClear ? ' is-clear' : ' is-blocked')}>
        <span className="gatekeeper-title">
          {clearedForExport
            ? 'Cleared for export'
            : gateClear
              ? 'High-risk entities resolved'
              : 'Gatekeeper check pending'}
        </span>
        <span className="gatekeeper-detail">
          {highRiskResolved.length} of {highRisk.length} high-risk entities resolved
          {run.reviewed_by ? ` · Reviewer: ${run.reviewed_by}` : ''}
        </span>
      </div>

      {error && <p className="upload-error">{error}</p>}

      <div className="run-header panel">
        <div>
          <h2 className="run-header-title">{run.script_title}</h2>
          <span className="run-header-sub">
            {run.reviewed_by ? `Last reviewed by ${run.reviewed_by}` : 'Not yet reviewed'}
          </span>
        </div>
        <span className={`status-pill status-pill--${run.overall_status}`}>
          {run.overall_status}
        </span>
      </div>

      {run.entities.map((entity) => (
        <div key={entity.entity_id} className="review-card-wrap">
          {entity.status !== 'flagged' && (
            <span className={`decision-stamp decision-stamp--${entity.status}`}>
              {entity.status === 'cleared'
                ? 'Approved'
                : entity.status === 'blocked'
                  ? 'Blocked'
                  : 'Dismissed'}
            </span>
          )}
          <EntityCard
            entity={entity}
            actions={
              <>
                <button
                  className="btn-ghost btn-small btn-success"
                  disabled={busyId === entity.entity_id || isLoading}
                  onClick={() => handleEntityDecision(entity.entity_id, 'cleared')}
                >
                  Approve
                </button>
                <button
                  className="btn-ghost btn-small btn-danger"
                  disabled={busyId === entity.entity_id || isLoading}
                  onClick={() => handleEntityDecision(entity.entity_id, 'blocked')}
                >
                  Block
                </button>
                <button
                  className="btn-ghost btn-small"
                  disabled={busyId === entity.entity_id || isLoading}
                  onClick={() => handleEntityDecision(entity.entity_id, 'overridden')}
                >
                  Dismiss
                </button>
              </>
            }
          />
        </div>
      ))}

      <div className="page-cta">
        <button
          className="btn-primary"
          disabled={!allReviewed}
          onClick={() => navigate('/reports')}
        >
          Generate report
        </button>
        <span className="page-cta-hint">
          {allReviewed
            ? 'All findings reviewed.'
            : `${reviewedCount} of ${run.entities.length} findings reviewed.`}
        </span>
      </div>
    </div>
  );
}
