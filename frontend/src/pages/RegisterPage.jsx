import React, { useState } from 'react';
import { authService } from '../services/auth';

export const RegisterPage = ({ onRegister }) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('user');
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);

  const handleRegister = async (e) => {
    e.preventDefault();
    setError(null);
    setSuccess(false);
    try {
      const result = await authService.register(username, password, role);
      if (result.success) {
        setSuccess(true);
        onRegister();
      } else {
        setError(result.error || 'Registration failed');
      }
    } catch (err) {
      setError('Registration failed');
    }
  };

  return (
    <div className="max-w-md mx-auto mt-16 bg-white rounded-lg shadow-lg p-8">
      <h2 className="text-2xl font-bold mb-6 text-center">Register</h2>
      <form onSubmit={handleRegister} className="space-y-4">
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
        <select
          value={role}
          onChange={e => setRole(e.target.value)}
          className="w-full px-4 py-2 border rounded-lg"
        >
          <option value="user">User</option>
          <option value="admin">Admin</option>
        </select>
        {error && <div className="text-red-500 text-sm">{error}</div>}
        {success && <div className="text-green-600 text-sm">Registration successful!</div>}
        <button type="submit" className="w-full bg-green-600 text-white py-2 rounded-lg font-semibold">Register</button>
      </form>
    </div>
  );
};
