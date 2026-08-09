import { Routes, Route, Outlet } from 'react-router-dom';
import ScrollStory from './ScrollStory';
import Features from './Features';
import AppHeader from './components/AppHeader';
import { RunProvider } from './context/RunContext';
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
  return (
    <div className="app-shell">
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
