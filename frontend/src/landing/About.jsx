import { useRef } from 'react';
import { useLenis } from '../lib/useLenis';
import { useRevealOnScroll } from '../lib/useRevealOnScroll';
import { useMaskReveal } from '../lib/useMaskReveal';
import { GeminiLogo, ParallelMark, FirebaseLogo, GoogleCloudLogo } from './logos/TechLogos';
import CustomCursor from './CustomCursor';
import Nav from './Nav';
import Footer from './Footer';
import './landing-shared.css';
import './About.css';

const HOW_IT_WORKS = [
  {
    title: 'Upload',
    text: 'A screenplay comes in as a PDF, Final Draft file, or plain text.',
  },
  {
    title: 'Extraction & grounding',
    text: "An agent reads the full script and extracts every entity worth flagging — business names, character names, songs, brands, addresses, phone numbers, license plates, quoted text, and real public figures — a fixed, deliberate list, not a free-for-all. A grounding-check pass filters out anything too weak or ambiguous to be worth researching.",
  },
  {
    title: 'Parallel research, three specialists at once',
    text: "Each flagged entity gets routed to the right kind of research — a business name doesn't need the same questions asked as a song title. Three specialist agents run simultaneously, each querying real-world sources via Parallel to check for actual matches: is this business real? Does this name collide with a real person? Is this song under active copyright? Every finding comes back with a cited source, not a guess.",
  },
  {
    title: 'Risk scoring',
    text: 'A scoring agent applies named, explainable rules to every entity and its research findings — not a black-box confidence number, but a specific rule that fired and why, so a reviewer can see exactly what triggered a flag.',
  },
  {
    title: 'Executive summary',
    text: 'The findings are distilled into a clear, scannable summary before anything reaches a human.',
  },
  {
    title: 'Legal review',
    text: "Every flagged entity is visible with its evidence, context, and script location. A reviewer with Legal's role — not a generic user — approves, accepts, or rejects each risk individually.",
  },
  {
    title: 'The gatekeeper',
    text: "Nothing gets exported until every high-risk item has been explicitly resolved. If anything is still outstanding, the run is held — regardless of what any earlier status says. This check exists specifically so a risk can't slip through by accident.",
  },
  {
    title: 'Report, exported',
    text: 'A structured clearance report is generated — accepted risks, outstanding risks, full evidence trail, and the audit information an insurer or legal team would actually need to sign off with confidence.',
  },
];

// "Cloud Firestore" reuses the Google Cloud mark — same convention
// StackStrip.jsx already uses, since there's no separate Firestore-specific
// logo asset in logos/TechLogos.jsx.
const BUILT_ON = [
  { name: 'Google Cloud', Logo: GoogleCloudLogo },
  { name: 'Gemini', Logo: GeminiLogo },
  { name: 'Parallel', Logo: ParallelMark },
  { name: 'Firestore', Logo: GoogleCloudLogo },
  { name: 'Firebase', Logo: FirebaseLogo },
];

// Generic section wrapper: the same "● LABEL" marker + heading + reveal
// treatment used throughout the landing page (RiskGrid, KeyFigures,
// Services, OurStory all follow this exact shape), reused here rather
// than inventing new section chrome for this page specifically.
function AboutSection({ marker, heading, headingClassName = 'about-heading', className = '', children }) {
  const sectionRef = useRef(null);
  const headingRef = useRef(null);
  useRevealOnScroll(sectionRef, { y: 24 });
  useMaskReveal(headingRef);

  return (
    <section className={`landing-section about-section ${className}`} ref={sectionRef}>
      {marker && <div className="section-marker">{marker}</div>}
      {heading && (
        <h2 className={headingClassName} ref={headingRef}>
          {heading}
        </h2>
      )}
      {children}
    </section>
  );
}

// Above-the-fold intro — mirrors Hero.jsx's own above-the-fold cascade
// (mask-reveal the headline, immediate rather than scroll-gated, since
// it's already in view on load) rather than the scroll-triggered reveal
// every other section on this page uses.
function AboutIntro() {
  const eyebrowRef = useRef(null);
  const headlineRef = useRef(null);
  const subRef = useRef(null);

  useMaskReveal(eyebrowRef, { immediate: true, delay: 0.15 });
  useMaskReveal(headlineRef, { immediate: true, delay: 0.28 });
  useMaskReveal(subRef, { immediate: true, delay: 0.44 });

  return (
    <header className="landing-section about-intro">
      <div className="section-marker" ref={eyebrowRef}>ABOUT SCRIPTCLEAR AI</div>
      <h1 className="about-intro-title" ref={headlineRef}>
        An AI agent crew for script clearance.
      </h1>
      <p className="about-intro-sub" ref={subRef}>
        ScriptClear AI reads a screenplay the way a clearance house would — finding every
        name, business, brand, and song that could pose a real legal risk — then
        researches, scores, and cites each one before a human ever has to sign off.
      </p>
    </header>
  );
}

function HowItWorksStep({ step, index }) {
  return (
    <li className="about-step">
      <span className="about-step-dot">{String(index + 1).padStart(2, '0')}</span>
      <div className="about-step-content">
        <h3 className="about-step-title">{step.title}</h3>
        <p className="about-step-text">{step.text}</p>
      </div>
    </li>
  );
}

// Same numbered-badge visual language as OurStory's "THE PIPELINE" (round,
// accent-bordered, monospace-numbered dots on a connecting rail) — laid
// out vertically, the way that same component already rotates to on
// mobile, since 8 steps here each carry a full title + paragraph rather
// than a single short label. The entrance is the same staggered
// scroll-triggered reveal (useRevealOnScroll) used everywhere else on
// this page, applied per-step, rather than a separate bespoke timeline.
function HowItWorks() {
  const sectionRef = useRef(null);
  const headingRef = useRef(null);
  useRevealOnScroll(sectionRef, { selector: '.about-step', stagger: 0.08, y: 24 });
  useMaskReveal(headingRef);

  return (
    <section className="landing-section about-section" ref={sectionRef}>
      <div className="section-marker">HOW IT WORKS</div>
      <h2 className="about-heading" ref={headingRef}>From script to a signed-off clearance report.</h2>
      <div className="about-steps-rail">
        <span className="about-steps-track" aria-hidden="true" />
        <ol className="about-steps">
          {HOW_IT_WORKS.map((step, i) => (
            <HowItWorksStep step={step} index={i} key={step.title} />
          ))}
        </ol>
      </div>
    </section>
  );
}

function BuiltOnBadge({ name, Logo }) {
  return (
    <span className="about-badge">
      <Logo className="about-badge-logo" />
      <span className="about-badge-name">{name}</span>
    </span>
  );
}

// Badges get their own small staggered entrance, distinct from the plain
// paragraph reveal above them — a trust/tech-stack signal, not more prose.
function BuiltOnStack() {
  const rowRef = useRef(null);
  useRevealOnScroll(rowRef, { selector: '.about-badge', stagger: 0.07, y: 14 });

  return (
    <div className="about-badges" ref={rowRef}>
      {BUILT_ON.map((item) => (
        <BuiltOnBadge {...item} key={item.name} />
      ))}
    </div>
  );
}

function ClosingLine() {
  const ref = useRef(null);
  useRevealOnScroll(ref, { y: 20 });

  return (
    <section className="landing-section about-closing" ref={ref}>
      <p className="about-closing-text">
        Script clearance shouldn&rsquo;t take weeks and a black box of guesswork.
        ScriptClear AI gives Legal a head start — with the receipts to back it up.
      </p>
    </section>
  );
}

export default function About() {
  useLenis();

  return (
    <div className="landing about-page">
      <CustomCursor />
      <Nav />
      <AboutIntro />

      <AboutSection marker="THE PROBLEM" heading="Clearance is still done by hand.">
        <div className="about-section-body">
          <p className="about-paragraph">
            Before a film or show can get Errors &amp; Omissions insurance, someone has to
            go through the entire script line by line, checking whether any character
            name, business, brand, or song lyric could trigger a real legal claim —
            defamation, trademark infringement, unauthorized use of a real person&rsquo;s
            likeness. Studios pay specialized &ldquo;clearance houses&rdquo; to do this by
            hand. It&rsquo;s slow, expensive, and every finding still has to be manually
            researched and justified before Legal will sign off.
          </p>
          <p className="about-paragraph">
            ScriptClear AI doesn&rsquo;t replace that judgment — it does the research and
            first pass so a human reviewer can focus on deciding, not searching.
          </p>
        </div>
      </AboutSection>

      <HowItWorks />

      <AboutSection marker="WHY CITED EVIDENCE MATTERS" heading="Every flag comes with a receipt.">
        <div className="about-section-body">
          <p className="about-paragraph">
            An AI flagging something as &ldquo;risky&rdquo; isn&rsquo;t useful on its own —
            a human still has to verify it before trusting it. Every finding ScriptClear AI
            produces comes with a real, checkable source: a trademark registration, a
            public database entry, a citation a reviewer can click through and confirm in
            seconds instead of researching from scratch.
          </p>
        </div>
      </AboutSection>

      <AboutSection marker="A HUMAN ALWAYS HAS THE FINAL WORD" heading="The decision always stays with a person.">
        <div className="about-section-body">
          <p className="about-paragraph">
            ScriptClear AI never approves anything on its own. Every clearance run is
            gated behind a Legal reviewer&rsquo;s sign-off, enforced through Google Cloud
            IAM and Firebase authentication — only an account explicitly marked as a legal
            reviewer can approve or reject a flagged risk. The system&rsquo;s job is to
            surface everything worth looking at, with evidence attached; the decision
            always stays with a person.
          </p>
        </div>
      </AboutSection>

      <AboutSection marker="BUILT ON" heading="The stack behind the pipeline.">
        <div className="about-section-body">
          <p className="about-paragraph">
            Google Cloud&rsquo;s Gemini Enterprise Agent Platform orchestrates the agent
            crew end to end. Gemini models handle extraction, reasoning, and
            summarization. Parallel powers the real-world research behind every citation.
            Firestore stores every run, finding, and decision. Firebase Authentication and
            Google Cloud IAM enforce who is actually allowed to approve a risk.
          </p>
        </div>
        <BuiltOnStack />
      </AboutSection>

      <ClosingLine />

      <Footer />
    </div>
  );
}
