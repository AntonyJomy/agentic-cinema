import './Footer.css';

// Palomino's footer has Infos/Pages/Socials/Legals/Credit columns plus a
// giant wordmark with photography showing through the letters. The
// Infos/Pages columns (hackathon note + Home/Sign in links) were removed
// by request — this keeps just the light-theme-flip + giant-wordmark
// structure, no link columns above it.
export default function Footer() {
  return (
    <footer className="landing-footer">
      <div className="footer-wordmark-wrap">
        <span className="footer-wordmark">SCRIPT CLEAR AI</span>
      </div>
    </footer>
  );
}
