import { useNavigate } from 'react-router-dom';
import { useRun } from '../context/useRun';
import EntityCard from '../components/EntityCard';
import { allEntitiesReviewed } from '../context/steps';
import '../styles/shared.css';
import './ReviewPage.css';

const REVIEWER_NAME = 'Ben Okafor (Legal)';

export default function ReviewPage() {
  const { run, updateEntityStatus, setOverallStatus } = useRun();
  const navigate = useNavigate();

  const highRisk = run.entities.filter((e) => e.requires_human_review);
  const highRiskResolved = highRisk.filter((e) => e.status !== 'flagged');
  const gateClear = highRisk.length === 0 || highRiskResolved.length === highRisk.length;

  const reviewedCount = run.entities.filter((e) => e.status !== 'flagged').length;
  const allReviewed = allEntitiesReviewed(run);

  return (
    <div className="app-page">
      <span className="page-eyebrow">STEP 4 · LEGAL REVIEW</span>
      <h1 className="page-title">Review &amp; decide</h1>
      <p className="page-sub">
        Approve, block, or dismiss each flagged entity. The run can't be
        approved until every high-risk entity has a decision.
      </p>

      <div className={'gatekeeper-banner' + (gateClear ? ' is-clear' : ' is-blocked')}>
        <span className="gatekeeper-title">
          {gateClear ? 'Gatekeeper check passed' : 'Gatekeeper check pending'}
        </span>
        <span className="gatekeeper-detail">
          {highRiskResolved.length} of {highRisk.length} high-risk entities resolved
        </span>
      </div>

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
              {entity.status === 'cleared' ? 'Cleared — Take 1' : 'Overridden'}
            </span>
          )}
          <EntityCard
            entity={entity}
            actions={
              <>
                <button
                  className="btn-ghost btn-small btn-success"
                  onClick={() => updateEntityStatus(entity.entity_id, 'cleared')}
                >
                  Approve
                </button>
                <button
                  className="btn-ghost btn-small btn-danger"
                  onClick={() => updateEntityStatus(entity.entity_id, 'flagged')}
                >
                  Block
                </button>
                <button
                  className="btn-ghost btn-small"
                  onClick={() => updateEntityStatus(entity.entity_id, 'overridden')}
                >
                  Dismiss
                </button>
              </>
            }
          />
        </div>
      ))}

      <div className="review-final panel">
        <div>
          <span className="run-header-title">Final decision</span>
          <span className="run-header-sub">
            {gateClear
              ? 'All high-risk entities are resolved — the run can be approved.'
              : 'Resolve every high-risk entity above before approving.'}
          </span>
        </div>
        <div className="review-final-actions">
          <button
            className="btn-ghost btn-danger"
            onClick={() => setOverallStatus('rejected', REVIEWER_NAME)}
          >
            Block run
          </button>
          <button
            className="btn-primary"
            disabled={!gateClear}
            onClick={() => setOverallStatus('approved', REVIEWER_NAME)}
          >
            Approve run
          </button>
        </div>
      </div>

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
