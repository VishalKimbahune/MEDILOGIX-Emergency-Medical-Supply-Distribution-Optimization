import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { Activity } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

export default function ProtectedRoute({ children }) {
  const { isAuthenticated, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-slate-50 px-4">
        <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-navy-900 text-teal-400 shadow-lg">
          <Activity className="h-6 w-6 animate-pulse" />
        </div>
        <p className="mt-4 text-sm font-semibold text-slate-700">
          Verifying MEDILOGIX session...
        </p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return children;
}
