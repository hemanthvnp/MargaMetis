import React from 'react';
import { AlertCircle } from 'lucide-react';

export const ErrorAlert = ({ error, onClose }) => {
  if (!error) return null;

  return (
    <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
      <div className="flex items-start">
        <AlertCircle className="w-5 h-5 text-red-600 mr-3 flex-shrink-0 mt-0.5" />
        <div className="flex-1">
          <h3 className="font-semibold text-red-800">Error</h3>
          <p className="text-red-700 text-sm mt-1">{error}</p>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="text-red-600 hover:text-red-800 font-semibold ml-2"
          >
            ✕
          </button>
        )}
      </div>
    </div>
  );
};
