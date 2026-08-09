import './Features.css';

const FEATURES = [
  {
    title: 'AI-powered analysis',
    desc: 'Understands your script deeply and extracts every entity that could represent a legal risk.',
    icon: (
      <path d="M12 3l1.6 4.4L18 9l-4.4 1.6L12 15l-1.6-4.4L6 9l4.4-1.6L12 3z" />
    ),
  },
  {
    title: 'Real-world research',
    desc: 'Agents search real sources via Parallel to find matches and potential conflicts.',
    icon: (
      <>
        <circle cx="10" cy="10" r="6.5" />
        <line x1="20" y1="20" x2="15" y2="15" />
      </>
    ),
  },
  {
    title: 'Cited evidence',
    desc: 'Every finding is backed by source links and documentation, ready for legal review.',
    icon: (
      <>
        <path d="M6 9h5M6 13h3" />
        <rect x="3" y="4" width="14" height="14" rx="2" />
        <path d="M17 15l3 3M20 18l-3-3" />
      </>
    ),
  },
  {
    title: 'Secure and compliant',
    desc: 'Built on Google Cloud with IAM approval gates. Nothing ships until Legal approves.',
    icon: <path d="M12 3l7 3v6c0 5-3.5 7.5-7 9-3.5-1.5-7-4-7-9V6l7-3z" />,
  },
  {
    title: 'Human-in-the-loop',
    desc: 'Legal reviews flagged risks, adds context, and makes the final call.',
    icon: (
      <>
        <circle cx="9" cy="8" r="3" />
        <circle cx="16" cy="9" r="2.5" />
        <path d="M3 20c0-3.5 2.7-6 6-6s6 2.5 6 6" />
        <path d="M15 14.3c2.5.3 4 2.3 4 5.7" />
      </>
    ),
  },
  {
    title: 'Insurance ready',
    desc: 'Generate clean, structured reports built for E&O insurers and legal teams.',
    icon: (
      <>
        <path d="M12 3l7 3v6c0 5-3.5 7.5-7 9-3.5-1.5-7-4-7-9V6l7-3z" />
        <path d="M9 12l2 2 4-4" />
      </>
    ),
  },
];

const TRUST_ITEMS = [
  'Google Cloud Infrastructure',
  'IAM Approval Gates',
  'SOC 2 Type II Compliant',
  'Data Never Used for Model Training',
];

export default function Features() {
  return (
    <section className="features">
      <div className="features-head">
        <span className="eyebrow">BUILT FOR MODERN FILMMAKERS AND STUDIOS</span>
        <h2>End-to-end script clearance, powered by AI.</h2>
      </div>

      <div className="feat-grid">
        {FEATURES.map((f) => (
          <div className="feat-card" key={f.title}>
            <div className="feat-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
                {f.icon}
              </svg>
            </div>
            <h3>{f.title}</h3>
            <p>{f.desc}</p>
            <a href="#" className="learn-more">Learn more <span aria-hidden="true">›</span></a>
          </div>
        ))}
      </div>

      <div className="trust-bar">
        <div className="trust-lead">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
            <rect x="5" y="11" width="14" height="9" rx="2" />
            <path d="M8 11V7a4 4 0 018 0v4" />
          </svg>
          Enterprise grade security
        </div>
        {TRUST_ITEMS.map((item) => (
          <span className="trust-item" key={item}>{item}</span>
        ))}
      </div>
    </section>
  );
}
