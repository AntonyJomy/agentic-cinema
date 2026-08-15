import RiskBadge from './RiskBadge';
import './EntityCard.css';

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

export default function EntityCard({ entity, actions }) {
  const {
    name,
    entity_type,
    risk_category,
    context,
    location,
    confidence,
    requires_human_review,
    evidence,
    status,
  } = entity;

  return (
    <div className="entity-card">
      <div className="entity-card-head">
        <div>
          <h3 className="entity-name">{name}</h3>
          <div className="entity-meta">
            <span>{TYPE_LABELS[entity_type] ?? entity_type}</span>
            <span className="entity-meta-dot">·</span>
            <span>{risk_category.replaceAll('_', ' ')}</span>
          </div>
        </div>
        <span className="entity-stamp">
          <RiskBadge status={status} />
        </span>
      </div>

      {requires_human_review && (
        <span className="entity-review-pill">Requires human review</span>
      )}

      <div className="entity-ticket-perf" aria-hidden="true" />

      <p className="entity-context">{context}</p>

      <div className="entity-location">
        {location.scene_number != null && <span>Scene {location.scene_number}</span>}
        {location.page_number != null && <span>Page {location.page_number}</span>}
        <span className="entity-excerpt">&ldquo;{location.line_excerpt}&rdquo;</span>
      </div>

      <div className="entity-confidence">
        <div className="confidence-track">
          <div
            className="confidence-fill"
            style={{ width: `${Math.round(confidence * 100)}%` }}
          />
        </div>
        <span>{Math.round(confidence * 100)}% extraction confidence</span>
      </div>

      {evidence.length > 0 ? (
        <ul className="entity-evidence">
          {evidence.map((ev) => (
            <li key={ev.source_url}>
              <a href={ev.source_url} target="_blank" rel="noreferrer">
                {ev.source_url}
              </a>
              <p>{ev.summary}</p>
            </li>
          ))}
        </ul>
      ) : (
        <p className="entity-no-evidence">No research evidence yet.</p>
      )}

      {actions && <div className="entity-actions">{actions}</div>}
    </div>
  );
}
