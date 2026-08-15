import { useNavigate } from 'react-router-dom';
import { useRun } from '../context/useRun';
import EntityCard from '../components/EntityCard';
import '../styles/shared.css';

export default function FindingsPage() {
  const { run } = useRun();
  const navigate = useNavigate();

  return (
    <div className="app-page">
      <span className="page-eyebrow">STEP 3 · FINDINGS</span>
      <h1 className="page-title">Clearance findings</h1>
      <p className="page-sub">
        Every entity the agent crew flagged, with the evidence gathered so
        far. Read-only — head to Review to make a call.
      </p>

      <div className="run-header panel">
        <div>
          <h2 className="run-header-title">{run.script_title}</h2>
          <span className="run-header-sub">
            {run.entities.length} entities · {run.metadata.total_pages_scanned} pages scanned
          </span>
        </div>
        <span className={`status-pill status-pill--${run.overall_status}`}>
          {run.overall_status}
        </span>
      </div>

      {run.entities.map((entity) => (
        <EntityCard key={entity.entity_id} entity={entity} />
      ))}

      <div className="page-cta">
        <button className="btn-primary" onClick={() => navigate('/review')}>
          Continue to review
        </button>
      </div>
    </div>
  );
}
