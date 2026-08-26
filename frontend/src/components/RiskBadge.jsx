import './RiskBadge.css';

const STATUS_CONFIG = {
  flagged: { label: 'Flagged', className: 'risk-badge--flagged' },
  cleared: { label: 'Cleared', className: 'risk-badge--cleared' },
  blocked: { label: 'Blocked', className: 'risk-badge--blocked' },
  overridden: { label: 'Overridden', className: 'risk-badge--overridden' },
};

export default function RiskBadge({ status }) {
  const config = STATUS_CONFIG[status] ?? STATUS_CONFIG.flagged;
  return <span className={`risk-badge ${config.className}`}>{config.label}</span>;
}
