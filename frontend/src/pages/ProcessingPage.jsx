import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useRun } from '../context/useRun';
import '../styles/shared.css';
import './ProcessingPage.css';

const PHASE_LABELS = {
  extraction: 'Extraction',
  grounding: 'Grounding',
  specialist: 'Research Specialists',
  risk_scoring: 'Risk Scoring',
  summary: 'Summary',
  legal_review: 'Legal Review',
  gatekeeper: 'Gatekeeper',
};

function formatDuration(seconds) {
  if (seconds == null) return null;
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return `${mins}m ${secs}s`;
}

function formatOutput(output) {
  if (!output) return null;
  try {
    return JSON.stringify(output, null, 2);
  } catch {
    return String(output);
  }
}

function agentState(event) {
  if (event.event === 'agent_start' && event.status === 'running') return 'active';
  if (event.event === 'agent_complete') {
    return event.status === 'failed' ? 'failed' : 'done';
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
  } = useRun();
  const [completed, setCompleted] = useState(false);

  useEffect(() => {
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
        });
        if (!cancelled) {
          setCompleted(true);
        }
      } catch {
        if (!cancelled) {
          setCompleted(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [
    pendingScript.scriptText,
    pendingScript.scriptTitle,
    runClearance,
    navigate,
    clearError,
  ]);

  const groupedEvents = useMemo(() => {
    const groups = new Map();
    for (const event of pipelineEvents) {
      const phase = event.phase || 'other';
      if (!groups.has(phase)) {
        groups.set(phase, []);
      }
      groups.get(phase).push(event);
    }
    return groups;
  }, [pipelineEvents]);

  const runningCount = pipelineEvents.filter(
    (event) => event.event !== 'agent_complete'
  ).length;
  const completedCount = pipelineEvents.filter(
    (event) => event.event === 'agent_complete'
  ).length;

  return (
    <div className="app-page">
      <span className="page-eyebrow">STEP 2 · PROCESSING</span>
      <h1 className="page-title">Running the clearance pipeline</h1>
      <p className="page-sub">
        {isLoading
          ? `Live agent feed — ${completedCount} completed${runningCount ? `, ${runningCount} running` : ''}.`
          : completed
            ? `Clearance pipeline complete${pipelineDuration != null ? ` in ${formatDuration(pipelineDuration)}` : ''}.`
            : 'Preparing clearance run…'}
      </p>

      <div className="panel agent-feed">
        {pipelineEvents.length === 0 && isLoading && (
          <p className="agent-feed-empty">Waiting for first agent to start…</p>
        )}

        {Array.from(groupedEvents.entries()).map(([phase, events]) => (
          <section key={phase} className="agent-phase">
            <h2 className="agent-phase-title">{PHASE_LABELS[phase] || phase}</h2>
            {events.map((event) => {
              const state = agentState(event);
              const label = event.entity_name
                ? `${event.agent_name} — ${event.entity_name}`
                : event.agent_name;

              return (
                <div key={event.key} className={`agent-row agent-row--${state}`}>
                  <div className="agent-row-header">
                    <div className="agent-marker">
                      {state === 'done' ? '✓' : state === 'failed' ? '!' : state === 'active' ? '…' : '·'}
                    </div>
                    <div className="agent-row-body">
                      <span className="agent-row-title">{label}</span>
                      {event.message && state === 'active' && (
                        <span className="agent-row-message">{event.message}</span>
                      )}
                      {event.duration_seconds != null && (
                        <span className="agent-row-duration">
                          {formatDuration(event.duration_seconds)}
                        </span>
                      )}
                    </div>
                    {state === 'active' && <div className="step-spinner" />}
                  </div>

                  {event.output && state !== 'active' && (
                    <details className="agent-output">
                      <summary>Agent output</summary>
                      <pre>{formatOutput(event.output)}</pre>
                    </details>
                  )}

                  {event.message && state === 'failed' && (
                    <p className="agent-row-error">{event.message}</p>
                  )}
                </div>
              );
            })}
          </section>
        ))}
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
