import { useEffect } from 'react';
import { Routes, Route, Outlet, Navigate, useLocation } from 'react-router-dom';
import LandingPage from './landing/LandingPage';
import AppHeader from './components/AppHeader';
import DustField from './components/DustField';
import { ProductTour, useTourState } from './components/ProductTour';
import { RunProvider } from './context/RunContext';
import { useRun } from './context/useRun';
import { STEPS, getMaxStepIndex } from './context/steps';
import { AuthProvider } from './auth/AuthContext';
import RequireAuth from './auth/RequireAuth';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import UploadPage from './pages/UploadPage';
import ProcessingPage from './pages/ProcessingPage';
import FindingsPage from './pages/FindingsPage';
import ReviewPage from './pages/ReviewPage';
import ReportsPage from './pages/ReportsPage';
import SettingsPage from './pages/SettingsPage';
import './styles/shared.css';
import './App.css';

function AppLayout({ tourState }) {
  const runCtx = useRun();
  const location = useLocation();
  const maxStep = getMaxStepIndex(runCtx);
  const currentStep = STEPS.findIndex((s) => s.path === location.pathname);

  // Trigger auto-start tour for first-time authenticated users
  useEffect(() => {
    if (tourState?.shouldAutoStart && !tourState.runTour) {
      const timer = setTimeout(() => {
        console.log('Auto-starting tour after successful auth');
        tourState.startTour();
      }, 1200);
      return () => clearTimeout(timer);
    }
  }, [tourState]);

  // Steps are sequential — jumping ahead (via nav, back button, or a typed
  // URL) bounces back to the furthest step the run has actually reached.
  // Non-step routes (e.g. /dashboard) are not gated.
  if (currentStep >= 0 && currentStep > maxStep) {
    return <Navigate to={STEPS[maxStep].path} replace />;
  }

  return (
    <div className="app-shell">
      <DustField />
      <AppHeader tourState={tourState} />
      <Outlet />
    </div>
  );
}

function App() {
  const tourState = useTourState();

  return (
    <AuthProvider>
      <RunProvider>
        <ProductTour run={tourState.runTour} onComplete={tourState.completeTour} />
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route
            element={
              <RequireAuth>
                <AppLayout tourState={tourState} />
              </RequireAuth>
            }
          >
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/upload" element={<UploadPage />} />
            <Route path="/processing" element={<ProcessingPage />} />
            <Route path="/findings" element={<FindingsPage />} />
            <Route path="/review" element={<ReviewPage />} />
            <Route path="/reports" element={<ReportsPage />} />
          </Route>
        </Routes>
      </RunProvider>
    </AuthProvider>
  );
}

export default App;
