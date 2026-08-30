import { useRef } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { useRevealOnScroll } from '../lib/useRevealOnScroll';
import { useMagnetic } from '../lib/useMagnetic';
import { useMaskReveal } from '../lib/useMaskReveal';
import './ClosingCta.css';

export default function ClosingCta() {
  const ref = useRef(null);
  const buttonRef = useRef(null);
  const titleRef = useRef(null);
  const { isAuthenticated } = useAuth();
  const ctaTo = isAuthenticated ? '/dashboard' : '/login';
  const ctaState = isAuthenticated ? undefined : { from: '/upload' };
  useRevealOnScroll(ref, { y: 32 });
  useMagnetic(buttonRef, { strength: 0.3 });
  useMaskReveal(titleRef);

  return (
    <section className="landing-section closing-cta" ref={ref}>
      <h2 className="closing-title" ref={titleRef}>
        LET&rsquo;S CLEAR
        <br />
        YOUR NEXT SCRIPT.
      </h2>
      <Link to={ctaTo} state={ctaState} className="closing-cta-button" ref={buttonRef}>
        START A CLEARANCE RUN →
      </Link>
    </section>
  );
}
