import { useState, useEffect, useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Joyride, STATUS, ACTIONS, EVENTS } from 'react-joyride';
import './ProductTour.css';

const TOUR_STORAGE_KEY = 'scriptclear-tour-completed';

const TOUR_STEPS = [
  {
    target: 'body',
    content: (
      <div>
        <h3>Welcome to ScriptClear AI</h3>
        <p>
          Here's how clearance works in 30 seconds. This is an AI-powered E&O
          clearance platform that reads your screenplay and flags every legal
          risk — trademarks, real people, locations, and more.
        </p>
      </div>
    ),
    placement: 'center',
    disableBeacon: true,
  },
  {
    target: '.dropzone',
    content: (
      <div>
        <h3>Upload your screenplay</h3>
        <p>
          Drop a screenplay PDF or paste text here to start a clearance run. Our
          agent crew reads it and flags every potential legal risk — character
          names, businesses, locations, literary references, and more.
        </p>
      </div>
    ),
    placement: 'bottom',
    disableBeacon: true,
  },
  {
    target: '.projector-track',
    content: (
      <div>
        <h3>Five-stage pipeline</h3>
        <p>
          Your script moves through these five stages automatically: Upload →
          Processing (entity extraction) → Findings (research) → Review (sign-off)
          → Reports (final clearance package).
        </p>
      </div>
    ),
    placement: 'bottom',
    disableBeacon: true,
  },
  {
    target: '.app-header-link[href="/dashboard"]',
    content: (
      <div>
        <h3>Your clearance dashboard</h3>
        <p>
          All your clearance runs and their risk summaries live here. Track
          high-risk items, see what's awaiting review, and access your cleared
          reports.
        </p>
      </div>
    ),
    placement: 'bottom',
    disableBeacon: true,
  },
  {
    target: 'body',
    content: (
      <div>
        <h3>Review & sign-off workflow</h3>
        <p>
          You approve, block, or dismiss each flagged risk. Nothing can be exported
          until every high-risk item is signed off — this is your governance layer
          that insurance underwriters trust.
        </p>
      </div>
    ),
    placement: 'center',
    disableBeacon: true,
  },
  {
    target: 'body',
    content: (
      <div>
        <h3>You're all set!</h3>
        <p>
          That's the clearance workflow. Upload a script above to begin your first
          run. The agent crew will extract entities, research them, and flag anything
          that needs legal attention.
        </p>
      </div>
    ),
    placement: 'center',
    disableBeacon: true,
  },
];

export function ProductTour({ run, onComplete }) {
  const navigate = useNavigate();
  const location = useLocation();
  const [isReady, setIsReady] = useState(false);
  const [hasNavigated, setHasNavigated] = useState(false);

  // Navigate to upload page and ensure we're ready before showing the tour
  useEffect(() => {
    if (run && !hasNavigated) {
      // Don't interfere with auth/login pages
      if (location.pathname === '/login' || location.pathname === '/') {
        console.log('Tour waiting - user on auth/landing page');
        return;
      }

      // Navigate to upload page ONCE if not already there
      if (location.pathname !== '/upload' && 
          !location.pathname.includes('/processing') &&
          !location.pathname.includes('/findings') &&
          !location.pathname.includes('/review') &&
          !location.pathname.includes('/reports')) {
        console.log('Navigating to upload page for tour');
        navigate('/upload');
        setHasNavigated(true);
      }
      
      // Small delay to ensure DOM is ready after navigation
      const timer = setTimeout(() => {
        console.log('Tour ready to start on', location.pathname);
        setIsReady(true);
      }, 500);
      return () => clearTimeout(timer);
    }
    
    // Reset navigation flag when tour is not running
    if (!run) {
      setIsReady(false);
      setHasNavigated(false);
    }
  }, [run, navigate, location.pathname, hasNavigated]);

  const handleJoyrideCallback = useCallback(
    (data) => {
      const { status, type, index } = data;

      console.log('Joyride event:', { status, type, index });

      // Handle completion or skip
      if ([STATUS.FINISHED, STATUS.SKIPPED].includes(status)) {
        console.log('Tour completed or skipped');
        setIsReady(false);
        setHasNavigated(false);
        if (onComplete) {
          onComplete();
        }
      }
    },
    [onComplete, setHasNavigated]
  );

  if (!run || !isReady) {
    return null;
  }

  return (
    <Joyride
      steps={TOUR_STEPS}
      run={true}
      continuous={true}
      showProgress={true}
      showSkipButton={true}
      callback={handleJoyrideCallback}
      disableOverlayClose={true}
      disableCloseOnEsc={false}
      scrollToFirstStep={true}
      spotlightPadding={8}
      styles={{
        options: {
          arrowColor: '#1a1a20',
          backgroundColor: '#1a1a20',
          overlayColor: 'rgba(0, 0, 0, 0.75)',
          primaryColor: '#d4a24c',
          textColor: '#f2f0ea',
          width: 380,
          zIndex: 10000,
        },
        tooltip: {
          borderRadius: '12px',
          padding: '20px',
          border: '1px solid rgba(212, 162, 76, 0.2)',
        },
        tooltipContent: {
          padding: '12px 0 0',
          textAlign: 'left',
        },
        buttonNext: {
          backgroundColor: '#d4a24c',
          color: '#14141a',
          borderRadius: '8px',
          padding: '10px 20px',
          fontSize: '14px',
          fontWeight: '600',
          fontFamily: "'Inter Tight', sans-serif",
          border: 'none',
          outline: 'none',
        },
        buttonBack: {
          color: 'rgba(242, 240, 234, 0.72)',
          marginRight: '12px',
          fontSize: '14px',
          fontFamily: "'Inter Tight', sans-serif",
        },
        buttonSkip: {
          color: 'rgba(242, 240, 234, 0.5)',
          fontSize: '13px',
          fontFamily: "'Inter Tight', sans-serif",
        },
        spotlight: {
          borderRadius: '8px',
          border: '2px solid #d4a24c',
          boxShadow: '0 0 0 9999px rgba(0, 0, 0, 0.75)',
        },
      }}
      locale={{
        back: 'Back',
        close: 'Close',
        last: 'Finish',
        next: 'Next',
        skip: 'Skip tour',
      }}
    />
  );
}

export function useTourState() {
  const [runTour, setRunTour] = useState(false);
  const [hasSeenTour, setHasSeenTour] = useState(true);
  const [shouldAutoStart, setShouldAutoStart] = useState(false);

  useEffect(() => {
    // Check if user has seen the tour
    const seen = localStorage.getItem(TOUR_STORAGE_KEY) === 'true';
    setHasSeenTour(seen);
    
    // Mark that we should auto-start if they haven't seen it
    if (!seen) {
      setShouldAutoStart(true);
    }
  }, []);

  const startTour = useCallback(() => {
    setRunTour(true);
    setShouldAutoStart(false);
  }, []);

  const completeTour = useCallback(() => {
    setRunTour(false);
    setShouldAutoStart(false);
    localStorage.setItem(TOUR_STORAGE_KEY, 'true');
    setHasSeenTour(true);
  }, []);

  return {
    runTour,
    hasSeenTour,
    shouldAutoStart,
    startTour,
    completeTour,
  };
}
