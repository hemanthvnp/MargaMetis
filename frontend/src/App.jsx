import React, { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Header }          from './components/Header';
import { HomePage }        from './pages/HomePage';
import { AuthModal }       from './components/AuthModal';
import { authService }     from './services/auth';
import { AdminDashboard }  from './pages/AdminDashboard';
import { UserDashboard }   from './pages/UserDashboard';
import { SpatialExplorer } from './pages/SpatialExplorer';
import './styles/globals.css';

function App() {
  const [user, setUser]         = useState(null);
  const [showAuth, setShowAuth] = useState(false);
  // Guarded routes must wait for /auth/me, or a reload of /user or /admin
  // redirects home before the session is known.
  const [authChecked, setAuthChecked] = useState(false);

  useEffect(() => {
    (async () => {
      const me = await authService.me();
      if (me?.logged_in) setUser({ username: me.username, role: me.role });
      setAuthChecked(true);
    })();
  }, []);

  const guard = (allowed, page) => {
    if (!authChecked) return null;
    return allowed ? page : <Navigate to="/" replace />;
  };

  return (
    <BrowserRouter>
      <div className="flex flex-col h-screen overflow-hidden bg-white">
        <Header
          user={user}
          onLoginClick={() => setShowAuth(true)}
          onLogoutClick={async () => {
            await authService.logout();
            setUser(null);
          }}
        />
        <main className="flex-1 overflow-hidden">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/spatial" element={<SpatialExplorer />} />
            <Route path="/admin"
              element={guard(user?.role === 'admin', <AdminDashboard />)} />
            <Route path="/user"
              element={guard(!!user, <UserDashboard />)} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
        <AuthModal
          open={showAuth}
          onClose={() => setShowAuth(false)}
          onSuccess={(u) => { setUser(u); setShowAuth(false); }}
        />
      </div>
    </BrowserRouter>
  );
}

export default App;
