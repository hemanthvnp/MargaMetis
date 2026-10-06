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

  useEffect(() => {
    (async () => {
      const me = await authService.me();
      if (me?.logged_in) setUser({ username: me.username, role: me.role });
    })();
  }, []);

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
              element={user?.role === 'admin' ? <AdminDashboard /> : <Navigate to="/" replace />} />
            <Route path="/user"
              element={user ? <UserDashboard /> : <Navigate to="/" replace />} />
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
