import { Routes, Route, Outlet, Navigate, useLocation } from 'react-router-dom';
import ScrollStory from './ScrollStory';
import Features from './Features';
import AppHeader from './components/AppHeader';
import DustField from './components/DustField';
import { RunProvider } from './context/RunContext';
import { useRun } from './context/useRun';
import { STEPS, getMaxStepIndex } from './context/steps';
import UploadPage from './pages/UploadPage';
import ProcessingPage from './pages/ProcessingPage';
import FindingsPage from './pages/FindingsPage';
import ReviewPage from './pages/ReviewPage';
import ReportsPage from './pages/ReportsPage';
import './styles/shared.css';
import './App.css';

function Landing() {
  return (
    <>
      <ScrollStory />
      <Features />
    </>
  );
}

function AppLayout() {
  const runCtx = useRun();
  const location = useLocation();
  const maxStep = getMaxStepIndex(runCtx);
  const currentStep = STEPS.findIndex((s) => s.path === location.pathname);

  // Steps are sequential — jumping ahead (via nav, back button, or a typed
  // URL) bounces back to the furthest step the run has actually reached.
  if (currentStep > maxStep) {
    return <Navigate to={STEPS[maxStep].path} replace />;
  }

  return (
    <div className="app-shell">
      <DustField />
      <AppHeader />
      <Outlet />
    </div>
  );
}

function App() {
  return (
    <RunProvider>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route element={<AppLayout />}>
          <Route path="/upload" element={<UploadPage />} />
          <Route path="/processing" element={<ProcessingPage />} />
          <Route path="/findings" element={<FindingsPage />} />
          <Route path="/review" element={<ReviewPage />} />
          <Route path="/reports" element={<ReportsPage />} />
        </Route>
      </Routes>
    </RunProvider>
  );
}

export default App;
