import { Link } from 'react-router-dom';
import './Footer.css';

// Palomino's footer has Infos/Pages/Socials/Legals/Credit columns plus a
// giant wordmark with photography showing through the letters. This keeps
// the light-theme-flip + giant-wordmark structure, but only includes
// columns with something real to say — no Socials or Legals columns, since
// there's no real social presence or terms page to link to, and a fake
// link to either would just be a dead end dressed up as real.
export default function Footer() {
  return (
    <footer className="landing-footer">
      <div className="landing-section footer-columns">
        <div className="footer-col">
          <span className="footer-col-label">INFOS</span>
          <p className="footer-note">Built for the Agentic Cinema hackathon.</p>
        </div>
        <div className="footer-col">
          <span className="footer-col-label">PAGES</span>
          <Link to="/">Home</Link>
          <Link to="/login">Sign in</Link>
        </div>
      </div>
      <div className="footer-wordmark-wrap">
        <span className="footer-wordmark">SCRIPTCLEAR</span>
      </div>
    </footer>
  );
}
