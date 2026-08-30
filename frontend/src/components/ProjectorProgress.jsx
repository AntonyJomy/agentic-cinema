import { useLocation } from 'react-router-dom';
import { useRun } from '../context/useRun';
import { STEPS, getMaxStepIndex } from '../context/steps';
import './ProjectorProgress.css';

function LockIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="5" y="11" width="14" height="9" rx="2" />
      <path d="M8 11V7a4 4 0 018 0v4" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 12l5 5L20 6" />
    </svg>
  );
}

export default function ProjectorProgress() {
  const runCtx = useRun();
  const location = useLocation();
  if (location.pathname === '/dashboard') {
    return null;
  }
  const maxStep = getMaxStepIndex(runCtx);
  const currentStep = Math.max(0, STEPS.findIndex((s) => s.path === location.pathname));
  const beamPercent = (currentStep / (STEPS.length - 1)) * 100;

  return (
    <div className="projector">
      <div className="projector-lamp" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <rect x="2" y="7" width="9" height="10" rx="1.5" />
          <circle cx="16.5" cy="12" r="4.5" />
          <circle cx="16.5" cy="12" r="1.3" fill="currentColor" stroke="none" />
        </svg>
      </div>

      <div className="projector-track">
        <div className="projector-beam" style={{ width: `${beamPercent}%` }} />

        {STEPS.map((step, i) => {
          const unlocked = i <= maxStep;
          const complete = i < currentStep && unlocked;
          const active = i === currentStep;
          const className =
            'projector-step' +
            (unlocked ? ' is-lit' : ' is-locked') +
            (active ? ' is-active' : '');
          // Positioned by exact percentage (not flex distribution) so nodes
          // land at precisely even intervals regardless of label width —
          // "Processing"/"Findings" are wider than "Upload"/"Review", which
          // threw off flexbox's space-between/space-evenly box-based spacing.
          const leftPercent = (i / (STEPS.length - 1)) * 100;

          const node = (
            <span className="projector-node">
              {!unlocked ? <LockIcon /> : complete ? <CheckIcon /> : i + 1}
            </span>
          );

          // Pure progress indicator — navigation happens via the CTA button
          // on each page, not by clicking ahead here.
          return (
            <span
              key={step.path}
              className={className}
              style={{ left: `${leftPercent}%` }}
              title={unlocked ? undefined : 'Complete the previous step first'}
            >
              {node}
              <span className="projector-label">{step.label}</span>
            </span>
          );
        })}
      </div>
    </div>
  );
}
