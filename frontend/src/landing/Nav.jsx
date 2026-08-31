import { useRef, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { ScrollTrigger, registerGsap, prefersReducedMotion } from '../lib/gsapConfig';
import './Nav.css';

export default function Nav() {
  const { isAuthenticated } = useAuth();
  const ctaTo = isAuthenticated ? '/dashboard' : '/login';
  const ctaState = isAuthenticated ? undefined : { from: '/upload' };
  const navRef = useRef(null);

  // Transparent at rest (reads over the hero), solidifies once the page has
  // scrolled past it — so it stays legible over whatever content sits under it.
  useEffect(() => {
    if (!navRef.current || prefersReducedMotion()) return undefined;
    registerGsap();

    const trigger = ScrollTrigger.create({
      start: 80,
      end: 99999,
      toggleClass: { targets: navRef.current, className: 'landing-nav--solid' },
    });

    return () => trigger.kill();
  }, []);

  return (
    <nav className="landing-nav" ref={navRef}>
      <Link to="/" className="landing-nav-mark">
        SCRIPT<span className="landing-nav-mark-accent">CLEAR</span> AI
      </Link>
      <div className="landing-nav-links">
        <Link to="/about" className="landing-nav-link">ABOUT</Link>
      </div>
      <Link to={ctaTo} state={ctaState} className="landing-nav-enter">
        SIGN IN
      </Link>
    </nav>
  );
}
