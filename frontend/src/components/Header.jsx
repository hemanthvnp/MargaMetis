import React from 'react';
import { Link } from 'react-router-dom';

export const Header = ({ user, onLoginClick, onLogoutClick }) => {
  return (
    <header className="bg-gradient-to-r from-blue-600 to-blue-800 text-white shadow-lg">
      <div className="max-w-7xl mx-auto px-4 py-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold">🗺️ MargaMetis</h1>
            <p className="text-blue-100 text-xs mt-1">Intelligent Route Optimizer</p>
          </div>
          <div className="flex items-center gap-4">
            <p className="text-blue-100 text-xs hidden sm:block">Powered by OSMnx & A* Algorithm</p>
            {user ? (
              <div className="flex items-center gap-3">
                <span className="text-sm bg-blue-700/50 px-3 py-1 rounded-md">
                  {user.username} · {user.role}
                </span>
                <Link
                  to="/user"
                  className="text-sm bg-white text-blue-700 hover:bg-blue-50 px-3 py-1 rounded-md"
                >
                  User
                </Link>
                {user.role === 'admin' && (
                  <Link
                    to="/admin"
                    className="text-sm bg-yellow-400 text-gray-900 hover:bg-yellow-500 px-3 py-1 rounded-md"
                  >
                    Admin
                  </Link>
                )}
                <button
                  onClick={onLogoutClick}
                  className="text-sm bg-red-600 hover:bg-red-700 px-3 py-1 rounded-md"
                >
                  Logout
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-3">
                <button
                  onClick={onLoginClick}
                  className="text-sm bg-white text-blue-700 hover:bg-blue-50 px-3 py-1 rounded-md"
                >
                  Login / Register
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
};
