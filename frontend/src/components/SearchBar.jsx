import React from 'react';
import { MapPin, Loader } from 'lucide-react';

export const SearchBar = ({ 
  origin, 
  destination, 
  onOriginChange, 
  onDestinationChange, 
  onSearch, 
  isLoading 
}) => {
  const handleSubmit = (e) => {
    e.preventDefault();
    onSearch();
  };

  return (
    <div className="w-full bg-white rounded-lg shadow-lg p-6">
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            <MapPin className="inline w-4 h-4 mr-2" />
            Origin
          </label>
          <input
            type="text"
            value={origin}
            onChange={(e) => onOriginChange(e.target.value)}
            placeholder="Enter origin location (e.g., Gandhipuram, Coimbatore)"
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            <MapPin className="inline w-4 h-4 mr-2" />
            Destination
          </label>
          <input
            type="text"
            value={destination}
            onChange={(e) => onDestinationChange(e.target.value)}
            placeholder="Enter destination location (e.g., Prozone Mall, Coimbatore)"
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition"
          />
        </div>

        <button
          type="submit"
          disabled={isLoading || !origin || !destination}
          className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white font-semibold py-2 px-4 rounded-lg transition flex items-center justify-center"
        >
          {isLoading ? (
            <>
              <Loader className="w-4 h-4 mr-2 animate-spin" />
              Calculating...
            </>
          ) : (
            'Find Route'
          )}
        </button>
      </form>
    </div>
  );
};
