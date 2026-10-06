import React from 'react';
import { Link } from 'react-router-dom';
import { Navigation2 } from 'lucide-react';

export const Header = ({ user, onLoginClick, onLogoutClick }) => (
  <header className="h-14 bg-white border-b border-gray-200 flex items-center px-4 z-50 shadow-sm">
    <Link to="/" className="flex items-center gap-2.5 flex-1 no-underline">
      <div className="w-7 h-7 bg-blue-600 rounded-md flex items-center justify-center">
        <Navigation2 className="w-4 h-4 text-white" />
      </div>
      <span className="font-semibold text-gray-900 text-base">MargaMetis</span>
      <span className="text-gray-300 hidden sm:block">·</span>
      <span className="text-xs text-gray-400 hidden sm:block">Graph Algorithms + LLM Route Intelligence</span>
    </Link>

    <div className="flex items-center gap-2">
      <Link to="/spatial"
        className="text-xs text-gray-600 hover:text-gray-900 px-3 py-1.5 rounded-md hover:bg-gray-100 transition">
        Spatial
      </Link>
      {user ? (
        <>
          <Link to="/user"
            className="text-xs text-gray-600 hover:text-gray-900 px-3 py-1.5 rounded-md hover:bg-gray-100 transition">
            History
          </Link>
          {user.role === 'admin' && (
            <Link to="/admin"
              className="text-xs bg-amber-50 text-amber-700 hover:bg-amber-100 px-3 py-1.5 rounded-md transition">
              Admin
            </Link>
          )}
          <span className="text-xs text-gray-400">{user.username}</span>
          <button onClick={onLogoutClick}
            className="text-xs text-gray-400 hover:text-gray-700 px-2 py-1.5 transition">
            Sign out
          </button>
        </>
      ) : (
        <button onClick={onLoginClick}
          className="text-xs bg-blue-600 hover:bg-blue-700 text-white px-4 py-1.5 rounded-md transition font-medium">
          Sign in
        </button>
      )}
    </div>
  </header>
);
