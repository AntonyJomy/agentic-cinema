import { useRef, useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from './auth/AuthContext';
import './ScrollStory.css';

const TOTAL_FRAMES = 240;
const frameUrl = (n) => `/frames/ezgif-frame-${String(n).padStart(3, '0')}.jpg`;
const VH_PER_STAGE = 120;

/** Dock magnification: max scale and influence radius in px. */
const DOCK_MAX_SCALE = 1.5;
const DOCK_INFLUENCE = 88;
const DOCK_LIFT_PX = 12;
/** How quickly smooth values chase the cursor (0–1 per frame @60fps). */
const DOCK_MOUSE_LERP = 0.18;
const DOCK_SCALE_LERP = 0.22;

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
    title: 'Clearance reports',
    desc: 'Export structured reports with findings, decisions, and warnings for legal teams.',
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

function dockScaleForDistance(distancePx) {
  if (distancePx >= DOCK_INFLUENCE) return 1;
  const t = 1 - distancePx / DOCK_INFLUENCE;
  // Cosine falloff — smooth neighbor magnification like macOS Dock
  const eased = 0.5 - 0.5 * Math.cos(Math.PI * t);
  return 1 + (DOCK_MAX_SCALE - 1) * eased;
}

function prefersReducedMotion() {
  return (
    typeof window !== 'undefined' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  );
}

function lerp(from, to, amount) {
  return from + (to - from) * amount;
}

export default function ScrollStory() {
  const { isAuthenticated } = useAuth();
  const ctaTo = isAuthenticated ? '/dashboard' : '/login';
  const ctaState = isAuthenticated ? undefined : { from: '/upload' };
  const wrapperRef = useRef(null);
  const imgRef = useRef(null);
  const itemRefs = useRef([]);
  const iconRefs = useRef([]);
  const dockRafRef = useRef(null);
  const dockTargetXRef = useRef(null);
  const dockSmoothXRef = useRef(null);
  const dockScalesRef = useRef(FEATURES.map(() => 1));
  const bounceIndexRef = useRef(null);
  const [displayIndex, setDisplayIndex] = useState(0);
  const [visible, setVisible] = useState(true);
  const [trail, setTrail] = useState(new Array(FEATURES.length).fill(0));
  const [bounceIndex, setBounceIndex] = useState(null);

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

  const applyDockTransforms = useCallback(() => {
    const reduceMotion = prefersReducedMotion();
    FEATURES.forEach((_, i) => {
      const icon = iconRefs.current[i];
      if (!icon) return;
      const scale = reduceMotion ? 1 : dockScalesRef.current[i];
      const lift = (scale - 1) * (DOCK_LIFT_PX / (DOCK_MAX_SCALE - 1));
      const bouncing = !reduceMotion && bounceIndexRef.current === i;
      icon.style.transform = bouncing
        ? `translateY(-${lift + 12}px) scale(${Math.max(scale, 1.32)})`
        : `translateY(-${lift}px) scale(${scale})`;
      icon.style.zIndex = String(Math.round(scale * 10));
    });
  }, []);

  const stopDockAnimation = useCallback(() => {
    if (dockRafRef.current != null) {
      cancelAnimationFrame(dockRafRef.current);
      dockRafRef.current = null;
    }
  }, []);

  const tickDock = useCallback(() => {
    const targetX = dockTargetXRef.current;
    let smoothX = dockSmoothXRef.current;

    if (targetX == null) {
      // Ease back to resting scales, then stop the loop.
      let stillMoving = false;
      dockScalesRef.current = dockScalesRef.current.map((scale) => {
        const next = lerp(scale, 1, DOCK_SCALE_LERP);
        if (Math.abs(next - 1) > 0.002) stillMoving = true;
        return next;
      });
      dockSmoothXRef.current = null;
      applyDockTransforms();
      if (stillMoving || bounceIndexRef.current != null) {
        dockRafRef.current = requestAnimationFrame(tickDock);
      } else {
        dockRafRef.current = null;
      }
      return;
    }

    if (smoothX == null) {
      smoothX = targetX;
    } else {
      smoothX = lerp(smoothX, targetX, DOCK_MOUSE_LERP);
    }
    dockSmoothXRef.current = smoothX;

    dockScalesRef.current = FEATURES.map((_, i) => {
      const el = itemRefs.current[i];
      let targetScale = 1;
      if (el) {
        const rect = el.getBoundingClientRect();
        const center = rect.left + rect.width / 2;
        targetScale = dockScaleForDistance(Math.abs(smoothX - center));
      }
      return lerp(dockScalesRef.current[i], targetScale, DOCK_SCALE_LERP);
    });

    applyDockTransforms();
    dockRafRef.current = requestAnimationFrame(tickDock);
  }, [applyDockTransforms]);

  const ensureDockAnimation = useCallback(() => {
    if (dockRafRef.current == null && !prefersReducedMotion()) {
      dockRafRef.current = requestAnimationFrame(tickDock);
    }
  }, [tickDock]);

  useEffect(() => () => stopDockAnimation(), [stopDockAnimation]);

  const handleDockMove = useCallback(
    (event) => {
      if (prefersReducedMotion()) return;
      dockTargetXRef.current = event.clientX;
      ensureDockAnimation();
    },
    [ensureDockAnimation]
  );

  const handleDockLeave = useCallback(() => {
    dockTargetXRef.current = null;
    ensureDockAnimation();
  }, [ensureDockAnimation]);

  const scrollToFeature = useCallback(
    (featureIndex) => {
      const wrapper = wrapperRef.current;
      if (!wrapper) return;

      bounceIndexRef.current = featureIndex;
      setBounceIndex(featureIndex);
      applyDockTransforms();
      ensureDockAnimation();
      window.setTimeout(() => {
        bounceIndexRef.current = null;
        setBounceIndex(null);
        applyDockTransforms();
      }, 480);

      // Feature i lives at stage i + 1 (stage 0 is intro)
      const stageIndex = featureIndex + 1;
      const total = wrapper.offsetHeight - window.innerHeight;
      if (total <= 0) return;
      const targetProgress = (stageIndex + 0.35) / STAGES.length;
      const top = wrapper.offsetTop + targetProgress * total;
      window.scrollTo({ top, behavior: 'smooth' });
    },
    [applyDockTransforms, ensureDockAnimation]
  );

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
                real-world evidence, and deliver structured clearance reports for
                human legal review.
              </p>
              <div className="cta-row">
                <Link className="btn-primary" to={ctaTo} state={ctaState}>
                  See it in action
                </Link>
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
                  <path d="M4 19V5" />
                  <path d="M4 19h16" />
                  <path d="M8 15V9" />
                  <path d="M12 15V7" />
                  <path d="M16 15v-4" />
                </svg>
              </div>
              <h2 className="feature-title">Ready to clear a script?</h2>
              <p className="feature-desc">
                Upload a screenplay, run the agent crew, review findings with legal,
                and export a clearance report.
              </p>
              <div className="cta-row">
                <Link className="btn-primary" to={ctaTo} state={ctaState}>
                  See it in action
                </Link>
              </div>
            </div>
          )}
        </div>

        <div
          className="story-trail"
          onMouseMove={handleDockMove}
          onMouseLeave={handleDockLeave}
          role="navigation"
          aria-label="Feature highlights"
        >
          {FEATURES.map((f, i) => (
            <button
              key={f.title}
              type="button"
              className={'trail-item' + (bounceIndex === i ? ' is-bouncing' : '')}
              ref={(node) => {
                itemRefs.current[i] = node;
              }}
              title={f.title}
              aria-label={`Go to ${f.title}`}
              onClick={() => scrollToFeature(i)}
            >
              <span
                className="trail-item-icon"
                ref={(node) => {
                  iconRefs.current[i] = node;
                }}
                style={{ opacity: 0.35 + trail[i] * 0.65 }}
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
                  {f.icon}
                </svg>
              </span>
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}
