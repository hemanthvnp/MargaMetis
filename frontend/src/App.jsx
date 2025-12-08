import React, { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Header } from './components/Header';
import { Footer } from './components/Footer';
import { HomePage } from './pages/HomePage';
import { AuthModal } from './components/AuthModal';
import { authService } from './services/auth';
import { AdminDashboard } from './pages/AdminDashboard';
import { UserDashboard } from './pages/UserDashboard';
import './styles/globals.css';

function App() {
  const [user, setUser] = useState(null); // { username, role }
  const [showAuth, setShowAuth] = useState(false);

  useEffect(() => {
    // Check current session
    (async () => {
      const me = await authService.me();
      if (me && me.logged_in) {
        setUser({ username: me.username, role: me.role });
      }
    })();
  }, []);

  const handleLogout = async () => {
    const res = await authService.logout();
    if (res && res.success) {
      setUser(null);
    }
  };

  return (
    <BrowserRouter>
      <div className="flex flex-col min-h-screen bg-gray-50">
        <Header
          user={user}
          onLoginClick={() => setShowAuth(true)}
          onLogoutClick={handleLogout}
        />
        <main className="flex-grow">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/admin" element={user?.role === 'admin' ? <AdminDashboard /> : <Navigate to="/" replace />} />
            <Route path="/user" element={user ? <UserDashboard /> : <Navigate to="/" replace />} />
          </Routes>
        </main>
        <Footer />
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
