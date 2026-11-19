import React from 'react';
import { Link } from 'react-router-dom';
import { Compass } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

export default function NotFound() {
  const { user, getPortalHome } = useAuth();
  const home = user ? getPortalHome(user.role) : '/login';

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-100 text-slate-600">
          <Compass className="h-7 w-7" />
        </div>
        <h1 className="mt-4 text-xl font-bold text-slate-900">Page Not Found (404)</h1>
        <p className="mt-2 text-sm text-slate-500">
          The page you requested does not exist in MEDILOGIX.
        </p>
        <Link
          to={home}
          className="mt-6 inline-flex items-center justify-center rounded-xl bg-navy-900 px-5 py-2.5 text-sm font-semibold text-white hover:bg-navy-800"
        >
          Go to Portal Home
        </Link>
      </div>
    </div>
  );
}
