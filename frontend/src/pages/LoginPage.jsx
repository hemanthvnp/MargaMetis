import React, { useState } from 'react';
import { authService } from '../services/auth';

export const LoginPage = ({ onLogin }) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);

  const handleLogin = async (e) => {
    e.preventDefault();
    setError(null);
    try {
      const result = await authService.login(username, password);
      if (result.success) {
        onLogin(result.role);
      } else {
        setError(result.error || 'Login failed');
      }
    } catch (err) {
      setError('Login failed');
    }
  };

  return (
    <div className="max-w-md mx-auto mt-16 bg-white rounded-lg shadow-lg p-8">
      <h2 className="text-2xl font-bold mb-6 text-center">Login</h2>
      <form onSubmit={handleLogin} className="space-y-4">
        <input
          type="text"
          placeholder="Username"
          value={username}
          onChange={e => setUsername(e.target.value)}
          className="w-full px-4 py-2 border rounded-lg"
        />
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={e => setPassword(e.target.value)}
          className="w-full px-4 py-2 border rounded-lg"
        />
        {error && <div className="text-red-500 text-sm">{error}</div>}
        <button type="submit" className="w-full bg-blue-600 text-white py-2 rounded-lg font-semibold">Login</button>
      </form>
    </div>
  );
};
