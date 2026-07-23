import { useState, useEffect } from 'react';
import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import axios from 'axios';
import Layout from './components/layout/Layout';
import SplashScreen from './pages/SplashScreen';
import WelcomeScreen from './pages/WelcomeScreen';
import CreateProfile from './pages/CreateProfile';
import ConsentScreen from './pages/ConsentScreen';
import Diagnostic from './pages/Diagnostic';
import Dashboard from './pages/Dashboard';
import UploadPDF from './pages/UploadPDF';
import GenerateTest from './pages/GenerateTest';
import SessionView from './pages/SessionView';
import OMRUpload from './pages/OMRUpload';
import Logs from './pages/Logs';
import CurrentAffairs from './pages/CurrentAffairs';
import CADetail from './pages/CADetail';
import MyTests from './pages/MyTests';
import ProfileAnalysis from './pages/ProfileAnalysis';
import MainsOcr from './pages/MainsOcr';

function waitForHealth(retries = 30, delay = 200) {
  return new Promise((resolve) => {
    const attempt = (n) => {
      axios.get('/api/health', { timeout: 1000 })
        .then(() => resolve())
        .catch(() => {
          if (n <= 0) return resolve(); // give up, let profile call fail gracefully
          setTimeout(() => attempt(n - 1), Math.min(delay, 2000));
        });
    };
    attempt(retries);
  });
}

const CACHE_KEY = 'upsc_profile_status';

export default function App() {
  const location = useLocation();
  const cached = sessionStorage.getItem(CACHE_KEY);
  const [status, setStatus] = useState(cached ? JSON.parse(cached) : null);

  useEffect(() => {
    let cancelled = false;
    waitForHealth().then(() => {
      if (cancelled) return;
      axios.get('/api/profile/status', { timeout: 3000 })
        .then((r) => {
          if (!cancelled) {
            setStatus(r.data);
            sessionStorage.setItem(CACHE_KEY, JSON.stringify(r.data));
          }
        })
        .catch(() => {
          if (!cancelled) setStatus({ registered: false, diagnostic_completed: false, name: null });
        });
    });
    return () => { cancelled = true; };
  }, [location.pathname]);

  if (!status) {
    return (
      <div className="h-screen w-screen flex items-center justify-center bg-[#0A0A0A]">
        <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-accent-blue to-accent-green flex items-center justify-center shadow-lg shadow-accent-blue/20">
          <span className="text-2xl font-bold text-white">U</span>
        </div>
      </div>
    );
  }

  // Not registered or diagnostic not complete — onboarding screens
  if (!status.registered || !status.diagnostic_completed) {
    return (
      <Routes>
        <Route path="/" element={<SplashScreen />} />
        <Route path="/welcome" element={<WelcomeScreen />} />
        <Route path="/create-profile" element={<CreateProfile />} />
        <Route path="/consent" element={<ConsentScreen />} />
        <Route path="/diagnostic" element={<Diagnostic standalone />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    );
  }

  // Fully onboarded — full app
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/upload" element={<UploadPDF />} />
        <Route path="/generate-test" element={<GenerateTest />} />
        <Route path="/session" element={<SessionView />} />
        <Route path="/session/:id" element={<SessionView />} />
        <Route path="/submit-omr" element={<OMRUpload />} />
        <Route path="/logs" element={<Logs />} />
        <Route path="/current-affairs" element={<CurrentAffairs />} />
        <Route path="/current-affairs/:id" element={<CADetail />} />
        <Route path="/my-tests" element={<MyTests />} />
        <Route path="/profile-analysis" element={<ProfileAnalysis />} />
        <Route path="/mains-ocr" element={<MainsOcr />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
