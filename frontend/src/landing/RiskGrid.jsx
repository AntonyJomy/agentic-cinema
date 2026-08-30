import { useRef } from 'react';
import { useRevealOnScroll } from '../lib/useRevealOnScroll';
import { useTilt } from '../lib/useTilt';
import { useScrollDepth } from '../lib/useScrollDepth';
import './RiskGrid.css';

// Palomino's "SELECTED PROJECTS" staggered image grid, structurally — but
// there are no real client screenplays to show, so this uses the seven
// actual risk categories the pipeline detects instead of fabricated
// project photography, in the same asymmetric offset layout.
const RISK_CATEGORIES = [
  { label: 'Business & Location', offset: 0 },
  { label: 'Character Name Collision', offset: 42 },
  { label: 'Music Rights', offset: 0 },
  { label: 'Trademark & Brand', offset: 64 },
  { label: 'PII Exposure', offset: 18 },
  { label: 'Literary Rights', offset: 0 },
  { label: 'Defamation Risk', offset: 36 },
];

function RiskTile({ label, index, offset }) {
  const ref = useRef(null);
  useTilt(ref, { max: 7 });
  useScrollDepth(ref, { speed: (index % 2 === 0 ? -1 : 1) * 0.06 });

  return (
    <div className="risk-tile" ref={ref} style={{ marginTop: `${offset}px` }}>
      <span className="risk-tile-index">{String(index + 1).padStart(2, '0')}</span>
      <span className="risk-tile-label">{label}</span>
    </div>
  );
}

export default function RiskGrid() {
  const ref = useRef(null);
  useRevealOnScroll(ref, { selector: '.risk-tile', stagger: 0.06 });

  return (
    <section className="landing-section risk-grid-section" ref={ref}>
      <div className="section-marker">WHAT WE SCREEN FOR</div>
      <div className="risk-grid">
        {RISK_CATEGORIES.map((r, i) => (
          <RiskTile key={r.label} label={r.label} index={i} offset={r.offset} />
        ))}
      </div>
    </section>
  );
}
