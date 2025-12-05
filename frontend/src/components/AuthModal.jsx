import React, { useState } from 'react';
import { authService } from '../services/auth';

export const AuthModal = ({ open, onClose, onSuccess }) => {
  const [tab, setTab] = useState('login'); // 'login' | 'register'
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('user');
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  if (!open) return null;

  const resetForm = () => {
    setUsername('');
    setPassword('');
    setRole('user');
    setError(null);
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const result = await authService.login(username, password);
      if (result.success) {
        onSuccess({ username, role: result.role });
        resetForm();
      } else {
        setError(result.error || 'Login failed');
      }
    } catch (err) {
      setError('Login failed');
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const result = await authService.register(username, password, role);
      if (result.success) {
        // Auto-switch to login after successful registration
        setTab('login');
      } else {
        setError(result.error || 'Registration failed');
      }
    } catch (err) {
      setError('Registration failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md">
        <div className="flex justify-between items-center border-b px-4 py-3">
          <div className="flex gap-2">
            <button
              className={`px-3 py-1 rounded-md text-sm ${tab === 'login' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-700'}`}
              onClick={() => { setTab('login'); setError(null); }}
            >
              Login
            </button>
            <button
              className={`px-3 py-1 rounded-md text-sm ${tab === 'register' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-700'}`}
              onClick={() => { setTab('register'); setError(null); }}
            >
              Register
            </button>
          </div>
          <button className="text-gray-500 hover:text-gray-700" onClick={() => { onClose(); resetForm(); }}>
            ✕
          </button>
        </div>

        <div className="p-4">
          {tab === 'login' ? (
            <form onSubmit={handleLogin} className="space-y-3">
              <input
                type="text"
                placeholder="Username"
                value={username}
                onChange={e => setUsername(e.target.value)}
                className="w-full px-3 py-2 border rounded-md"
              />
              <input
                type="password"
                placeholder="Password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                className="w-full px-3 py-2 border rounded-md"
              />
              {error && <div className="text-red-600 text-sm">{error}</div>}
              <button
                type="submit"
                disabled={loading}
                className="w-full bg-blue-600 hover:bg-blue-700 text-white py-2 rounded-md"
              >
                {loading ? 'Logging in...' : 'Login'}
              </button>
            </form>
          ) : (
            <form onSubmit={handleRegister} className="space-y-3">
              <input
                type="text"
                placeholder="Username"
                value={username}
                onChange={e => setUsername(e.target.value)}
                className="w-full px-3 py-2 border rounded-md"
              />
              <input
                type="password"
                placeholder="Password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                className="w-full px-3 py-2 border rounded-md"
              />
              <select
                value={role}
                onChange={e => setRole(e.target.value)}
                className="w-full px-3 py-2 border rounded-md"
              >
                <option value="user">User</option>
                <option value="admin">Admin</option>
              </select>
              {error && <div className="text-red-600 text-sm">{error}</div>}
              <button
                type="submit"
                disabled={loading}
                className="w-full bg-green-600 hover:bg-green-700 text-white py-2 rounded-md"
              >
                {loading ? 'Registering...' : 'Register'}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
