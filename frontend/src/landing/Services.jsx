import { useRef, useEffect } from 'react';
import { useRevealOnScroll } from '../lib/useRevealOnScroll';
import { useTilt } from '../lib/useTilt';
import { useMaskReveal } from '../lib/useMaskReveal';
import { gsap, registerGsap, prefersReducedMotion } from '../lib/gsapConfig';
import './Services.css';

// Palomino's repeated "SERVICES" card — numbered visual, heading +
// description, right-column capability list. Mapped one-to-one onto the
// real specialist agents in agents/, grouped by the risk category they
// research (schemas/entities.py RiskCategory) — real functionality, not
// invented feature copy.
// Each `video` path is a placeholder — no licensed footage has been
// sourced yet. See VIDEO_REQUIREMENTS.md for exactly what each file needs
// to show; drop a matching MP4 at the path and it starts playing with no
// further code changes. Until then the existing amber gradient in
// .service-visual (Services.css) shows through as a graceful fallback —
// a <video> with a missing src renders as nothing, not a broken-image icon.
const SERVICES = [
  {
    index: '01',
    tag: 'BUSINESS & BRAND',
    title: 'Every logo, storefront and trademark, verified.',
    description:
      'The business and trademark specialists check any named company, brand, or logo against real-world registrations — flagging depictions that could expose a production to trademark or defamation risk.',
    capabilities: [
      'Brand & logo detection',
      'Trademark search',
      'Business name matching',
      'Real-world verification',
    ],
    video: '/videos/agents/business-brand.mp4',
  },
  {
    index: '02',
    tag: 'CHARACTER & IDENTITY',
    title: 'Fictional names, checked against real people.',
    description:
      'The character-name specialist researches whether a named character could plausibly be mistaken for a real, identifiable person — the single most common source of defamation exposure in a screenplay.',
    capabilities: [
      'Name collision detection',
      'Public figure matching',
      'Demographic research',
      'Defamation risk scoring',
    ],
    video: '/videos/agents/character-identity.mp4',
  },
  {
    index: '03',
    tag: 'MUSIC & LITERARY',
    title: 'Lyrics, quotes and references, sourced.',
    description:
      'Music and literary-reference specialists trace every song lyric, book quote, or cultural reference back to its rights holder, so licensing conversations start with evidence instead of guesswork.',
    capabilities: [
      'Song rights detection',
      'Quote attribution',
      'Copyright research',
      'Licensing flags',
    ],
    video: '/videos/agents/music-literary.mp4',
  },
  {
    index: '04',
    tag: 'PRIVACY & LOCATION',
    title: 'Addresses and numbers, before they air.',
    description:
      'The address specialist verifies whether a shown street address, phone number, or license plate resolves to a real, identifiable location — a quiet but real privacy-exposure risk.',
    capabilities: [
      'Address verification',
      'Phone number detection',
      'License plate screening',
      'Privacy risk assessment',
    ],
    video: '/videos/agents/privacy-location.mp4',
  },
];

function ServiceCard({ s, reverse }) {
  const cardRef = useRef(null);
  const visualRef = useRef(null);
  const titleRef = useRef(null);
  useTilt(visualRef, { max: 5 });
  useMaskReveal(titleRef);

  // Sticks at the top of the viewport, then flattens slightly as the next
  // card arrives and covers it — the stacked-cards technique, scaled to
  // this section's compact row height rather than full-screen panels.
  useEffect(() => {
    if (!cardRef.current || prefersReducedMotion()) return undefined;
    registerGsap();

    const ctx = gsap.context(() => {
      gsap.to(cardRef.current, {
        scaleY: 0.94,
        ease: 'none',
        scrollTrigger: {
          trigger: cardRef.current,
          start: 'top 90px',
          end: 'bottom 90px',
          scrub: true,
        },
      });
    }, cardRef);

    return () => ctx.revert();
  }, []);

  return (
    <article className={`service-card${reverse ? ' service-card--reverse' : ''}`} ref={cardRef}>
      <div className="service-visual" ref={visualRef}>
        <video
          className="service-visual-video"
          src={s.video}
          autoPlay
          muted
          loop
          playsInline
          preload="metadata"
          aria-hidden="true"
        />
        <span className="service-index">{s.index}.</span>
        <span className="service-visual-tag">{s.tag}</span>
      </div>
      <div className="service-body">
        <h3 className="service-title" ref={titleRef}>{s.title}</h3>
        <p className="service-description">{s.description}</p>
      </div>
      <div className="service-capabilities">
        <span className="service-capabilities-label">CAPABILITIES:</span>
        <ul>
          {s.capabilities.map((c) => (
            <li key={c}>{c}</li>
          ))}
        </ul>
      </div>
    </article>
  );
}

export default function Services() {
  const ref = useRef(null);
  useRevealOnScroll(ref, { selector: '.service-card', stagger: 0.1, y: 32 });

  return (
    <section className="landing-section services-section" ref={ref}>
      <div className="section-marker">SPECIALIST AGENTS</div>
      {SERVICES.map((s, i) => (
        <ServiceCard s={s} reverse={i % 2 === 1} key={s.index} />
      ))}
    </section>
  );
}
