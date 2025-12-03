import React from 'react';

export const Header = () => {
  return (
    <header className="bg-gradient-to-r from-blue-600 to-blue-800 text-white shadow-lg">
      <div className="max-w-7xl mx-auto px-4 py-6 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-4xl font-bold">🗺️ MargaMetis</h1>
            <p className="text-blue-100 text-sm mt-1">Intelligent Route Optimizer</p>
          </div>
          <div className="text-right text-sm">
            <p className="text-blue-100">Powered by OSMnx & A* Algorithm</p>
          </div>
        </div>
      </div>
    </header>
  );
};
