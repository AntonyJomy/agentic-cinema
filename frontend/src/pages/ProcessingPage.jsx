import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import '../styles/shared.css';
import './ProcessingPage.css';

const STEPS = [
  { title: 'Read & Clean', detail: 'Extraction + Grounding Check Agents' },
  { title: 'Research', detail: '3 specialists in parallel — Business, Name, Music' },
  { title: 'Score each risk', detail: 'Scoring Agent — named rule + evidence' },
  { title: 'Summarize', detail: 'Executive Summary Agent' },
];

const STEP_MS = 1100;

export default function ProcessingPage() {
  const navigate = useNavigate();
  const [activeStep, setActiveStep] = useState(0);
  const done = activeStep >= STEPS.length;

  useEffect(() => {
    if (done) return;
    const timer = setTimeout(() => setActiveStep((s) => s + 1), STEP_MS);
    return () => clearTimeout(timer);
  }, [activeStep, done]);

  return (
    <div className="app-page">
      <span className="page-eyebrow">STEP 2 · PROCESSING</span>
      <h1 className="page-title">Running the clearance pipeline</h1>
      <p className="page-sub">
        The agent crew is reading the script, researching every flagged
        entity, and scoring the results.
      </p>

      <div className="panel stepper">
        {STEPS.map((step, i) => {
          const state = i < activeStep ? 'done' : i === activeStep ? 'active' : 'pending';
          return (
            <div key={step.title} className={`step step--${state}`}>
              <div className="step-marker">
                {state === 'done' ? '✓' : i + 1}
              </div>
              <div className="step-body">
                <span className="step-title">{step.title}</span>
                <span className="step-detail">{step.detail}</span>
              </div>
              {state === 'active' && <div className="step-spinner" />}
            </div>
          );
        })}
      </div>

      <div className="processing-cta">
        <button
          className="btn-primary"
          disabled={!done}
          onClick={() => navigate('/findings')}
        >
          {done ? 'View findings' : 'Processing…'}
        </button>
      </div>
    </div>
  );
}
