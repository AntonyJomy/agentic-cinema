import { useRef, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import './ScrollStory.css';

const TOTAL_FRAMES = 240;
const frameUrl = (n) => `/frames/ezgif-frame-${String(n).padStart(3, '0')}.jpg`;
const VH_PER_STAGE = 120;

const FEATURES = [
  {
    title: 'AI-powered analysis',
    desc: 'Understands your script deeply and extracts every entity that could represent a legal risk.',
    icon: <path d="M12 3l1.6 4.4L18 9l-4.4 1.6L12 15l-1.6-4.4L6 9l4.4-1.6L12 3z" />,
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

const STAGES = [
  { type: 'intro' },
  ...FEATURES.map((f) => ({ type: 'feature', ...f })),
  { type: 'closing' },
];

// Must match the opacity transition duration in ScrollStory.css (.story-content)
const FADE_MS = 260;

export default function ScrollStory() {
  const wrapperRef = useRef(null);
  const imgRef = useRef(null);
  const [displayIndex, setDisplayIndex] = useState(0);
  const [visible, setVisible] = useState(true);
  const [trail, setTrail] = useState(new Array(FEATURES.length).fill(0));

  useEffect(() => {
    const wrapper = wrapperRef.current;
    if (!wrapper) return;

    const displayIndexRef = { current: 0 };
    const targetIndexRef = { current: 0 };
    const transitioning = { current: false };
    let timeoutId = null;

    // Crossfades on a fixed timer, not scroll position, so a fade always
    // finishes (fully shown or fully hidden) even if the user stops
    // scrolling mid-transition. Chases the latest target once it settles.
    function goToTarget() {
      if (targetIndexRef.current === displayIndexRef.current) return;
      transitioning.current = true;
      setVisible(false);
      timeoutId = setTimeout(() => {
        displayIndexRef.current = targetIndexRef.current;
        setDisplayIndex(displayIndexRef.current);
        setVisible(true);
        timeoutId = setTimeout(() => {
          transitioning.current = false;
          goToTarget();
        }, FADE_MS);
      }, FADE_MS);
    }

    function update() {
      const rect = wrapper.getBoundingClientRect();
      const total = rect.height - window.innerHeight;
      const progress = Math.max(0, Math.min(1, -rect.top / total));

      const frameIndex = Math.round(progress * (TOTAL_FRAMES - 1)) + 1;
      if (imgRef.current) imgRef.current.src = frameUrl(frameIndex);

      const raw = progress * STAGES.length;
      const idx = Math.min(STAGES.length - 1, Math.floor(raw));

      targetIndexRef.current = idx;
      if (!transitioning.current && idx !== displayIndexRef.current) {
        goToTarget();
      }

      // Progress trail: each feature fills in permanently once you've moved past its stage
      const newTrail = FEATURES.map((_, i) => {
        const stageOfFeature = i + 1; // stage 0 is intro
        return Math.max(0, Math.min(1, raw - stageOfFeature));
      });
      setTrail(newTrail);
    }

    window.addEventListener('scroll', update);
    window.addEventListener('resize', update);
    update();

    return () => {
      window.removeEventListener('scroll', update);
      window.removeEventListener('resize', update);
      clearTimeout(timeoutId);
    };
  }, []);

  const stage = STAGES[displayIndex];
  const wrapperHeight = `${STAGES.length * VH_PER_STAGE}vh`;

  return (
    <div className="story-wrapper" ref={wrapperRef} style={{ height: wrapperHeight }}>
      <section className="story-pin">
        <img ref={imgRef} className="story-bg" src={frameUrl(1)} alt="" aria-hidden="true" />
        <div className="story-scrim"></div>

        <div className="story-content" style={{ opacity: visible ? 1 : 0 }}>
          {stage.type === 'intro' && (
            <>
              <span className="eyebrow">AI AGENT CREW FOR FILM E&amp;O CLEARANCE</span>
              <h1>Clear scripts.<br />Protect stories.</h1>
              <p className="story-sub">
                ScriptClear AI uses an agent crew to identify legal risks, research
                real-world evidence, and deliver insurance-ready clearance reports —
                faster and with confidence.
              </p>
              <div className="cta-row">
                <Link className="btn-primary" to="/upload">See it in action</Link>
                <button className="btn-ghost">How it works</button>
              </div>
              <p className="scroll-hint">Scroll to explore ↓</p>
            </>
          )}

          {stage.type === 'feature' && (
            <div className="glass-card">
              <div className="feature-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
                  {stage.icon}
                </svg>
              </div>
              <h2 className="feature-title">{stage.title}</h2>
              <p className="feature-desc">{stage.desc}</p>
            </div>
          )}

          {stage.type === 'closing' && (
            <div className="glass-card">
              <div className="feature-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="5" y="11" width="14" height="9" rx="2" />
                  <path d="M8 11V7a4 4 0 018 0v4" />
                </svg>
              </div>
              <h2 className="feature-title">Enterprise grade security</h2>
              <p className="feature-desc">
                Google Cloud infrastructure, IAM approval gates, Firebase authentication,
                and a full audit trail on every decision.
              </p>
              <div className="cta-row">
                <Link className="btn-primary" to="/upload">Book a demo</Link>
              </div>
            </div>
          )}
        </div>

        <div className="story-trail">
          {FEATURES.map((f, i) => (
            <div
              key={f.title}
              className="trail-item"
              style={{ opacity: 0.35 + trail[i] * 0.65 }}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
                {f.icon}
              </svg>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
