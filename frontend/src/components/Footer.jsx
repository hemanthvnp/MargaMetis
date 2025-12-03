import React from 'react';

export const Footer = () => {
  return (
    <footer className="bg-gray-800 text-gray-300 mt-12">
      <div className="max-w-7xl mx-auto px-4 py-8 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          <div>
            <h3 className="text-white font-semibold mb-3">About MargaMetis</h3>
            <p className="text-sm">
              An intelligent route optimization platform using advanced pathfinding
              algorithms and real-time map data.
            </p>
          </div>
          <div>
            <h3 className="text-white font-semibold mb-3">Technology</h3>
            <ul className="text-sm space-y-1">
              <li>• React & Tailwind CSS</li>
              <li>• Flask Backend</li>
              <li>• OSMnx & NetworkX</li>
              <li>• A* Algorithm</li>
            </ul>
          </div>
          <div>
            <h3 className="text-white font-semibold mb-3">Contact</h3>
            <p className="text-sm">
              For more information or support, please visit our repository.
            </p>
          </div>
        </div>
        <div className="border-t border-gray-700 mt-8 pt-8 text-center text-sm">
          <p>&copy; 2024 MargaMetis. All rights reserved.</p>
        </div>
      </div>
    </footer>
  );
};
