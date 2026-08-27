import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useRun } from '../context/useRun';
import '../styles/shared.css';
import './ProcessingPage.css';

const STAGES = [
  { id: 'received', label: 'Upload received' },
  { id: 'extraction', label: 'Extracting script' },
  { id: 'analysis', label: 'Running analysis' },
  { id: 'research', label: 'Running specialist reviews' },
  { id: 'risks', label: 'Evaluating risks' },
  { id: 'summary', label: 'Preparing summary' },
  { id: 'legal_review', label: 'Preparing legal review' },
  { id: 'gatekeeper', label: 'Running gatekeeper' },
];

function formatDuration(seconds) {
  if (seconds == null) return null;
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return `${mins}m ${secs}s`;
}

function stageState(events, stageId, isLoading, completed) {
  const matching = events.filter((event) => event.stage === stageId);
  if (matching.some((event) => event.status === 'failed')) return 'failed';
  if (matching.some((event) => event.status === 'completed')) return 'done';
  if (matching.some((event) => event.status === 'running')) return 'active';
  if (completed) return 'done';
  if (isLoading) {
    const firstPending = STAGES.find((stage) => {
      const hits = events.filter((event) => event.stage === stage.id);
      return !hits.some((event) => event.status === 'completed');
    });
    if (firstPending?.id === stageId) return 'active';
  }
  return 'pending';
}

export default function ProcessingPage() {
  const navigate = useNavigate();
  const {
    pendingScript,
    runClearance,
    isLoading,
    error,
    clearError,
    pipelineEvents,
    pipelineDuration,
    lastResponse,
  } = useRun();
  const [completed, setCompleted] = useState(Boolean(lastResponse?.run?.run_id));

  useEffect(() => {
    if (lastResponse?.run?.run_id) {
      setCompleted(true);
      return;
    }
    if (!pendingScript.scriptText) {
      navigate('/upload', { replace: true });
      return;
    }

    let cancelled = false;
    clearError();

    (async () => {
      try {
        await runClearance({
          scriptText: pendingScript.scriptText,
          scriptTitle: pendingScript.scriptTitle,
          sourceFileName: pendingScript.sourceFileName,
        });
        if (!cancelled) setCompleted(true);
      } catch {
        if (!cancelled) setCompleted(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [
    pendingScript.scriptText,
    pendingScript.scriptTitle,
    pendingScript.sourceFileName,
    runClearance,
    navigate,
    clearError,
    lastResponse?.run?.run_id,
  ]);

  const latestCounts = useMemo(() => {
    const counts = {};
    for (const event of pipelineEvents) {
      if (event.stage && typeof event.count === 'number') {
        counts[event.stage] = event.count;
      }
    }
    return counts;
  }, [pipelineEvents]);

  return (
    <div className="app-page">
      <span className="page-eyebrow">STEP 2 · PROCESSING</span>
      <h1 className="page-title">Running the clearance pipeline</h1>
      <p className="page-sub">
        {isLoading
          ? 'Live progress — extraction, research, risk scoring, and gatekeeper.'
          : completed
            ? `Clearance pipeline complete${pipelineDuration != null ? ` in ${formatDuration(pipelineDuration)}` : ''}.`
            : 'Preparing clearance run…'}
      </p>

      <div className="panel filmstrip-frame agent-feed-outer">
        <div className="agent-feed">
          {STAGES.map((stage) => {
            const state = stageState(pipelineEvents, stage.id, isLoading, completed);
            const count = latestCounts[stage.id];
            return (
              <div key={stage.id} className={`agent-row agent-row--${state}`}>
                <div className="agent-row-header">
                  <div className="agent-marker">
                    {state === 'done' ? '✓' : state === 'failed' ? '!' : state === 'active' ? '…' : '·'}
                  </div>
                  <div className="agent-row-body">
                    <span className="agent-row-title">{stage.label}</span>
                    {typeof count === 'number' && (
                      <span className="agent-row-message">{count} item{count === 1 ? '' : 's'}</span>
                    )}
                  </div>
                  {state === 'active' && <div className="step-spinner" />}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {error && (
        <div className="panel processing-error">
          <p>{error}</p>
          <button className="btn-ghost" onClick={() => navigate('/upload')}>
            Back to upload
          </button>
        </div>
      )}

      <div className="processing-cta">
        <button
          className="btn-primary"
          disabled={!completed || isLoading}
          onClick={() => navigate('/findings')}
        >
          {completed ? 'View findings' : 'Processing…'}
        </button>
      </div>
    </div>
  );
}
