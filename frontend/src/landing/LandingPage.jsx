import { useLenis } from '../lib/useLenis';
import PageIntro from './PageIntro';
import CustomCursor from './CustomCursor';
import Nav from './Nav';
import Hero from './Hero';
import StackStrip from './StackStrip';
import RiskGrid from './RiskGrid';
import KeyFigures from './KeyFigures';
import Services from './Services';
import OurStory from './OurStory';
import PipelineCarousel from './PipelineCarousel';
import ClosingCta from './ClosingCta';
import Footer from './Footer';
import './landing-shared.css';

// Structurally cloned from palominoprod.com/en, section for section: hero
// -> trusted-by strip -> project grid -> key figures -> services -> story
// -> testimonial carousel -> closing CTA -> footer with giant wordmark.
// Every section keeps that structure but carries real ScriptClear content
// — no fabricated client logos, project photos, usage stats, or customer
// endorsements anywhere (see the comment at the top of each section file
// for what was substituted and why).
export default function LandingPage() {
  useLenis();

  return (
    <div className="landing">
      <PageIntro />
      <CustomCursor />
      <Nav />
      <Hero />
      <StackStrip />
      <RiskGrid />
      <KeyFigures />
      <Services />
      <OurStory />
      <PipelineCarousel />
      <ClosingCta />
      <Footer />
    </div>
  );
}
