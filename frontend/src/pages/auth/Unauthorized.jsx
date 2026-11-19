import React from 'react';
import { Link } from 'react-router-dom';
import { ShieldAlert } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

export default function Unauthorized() {
  const { user, getPortalHome } = useAuth();
  const home = user ? getPortalHome(user.role) : '/login';

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-red-50 text-red-600">
          <ShieldAlert className="h-7 w-7" />
        </div>
        <h1 className="mt-4 text-xl font-bold text-slate-900">Access Restricted (403)</h1>
        <p className="mt-2 text-sm text-slate-500">
          Your role ({user?.role?.toUpperCase() || 'GUEST'}) does not have permission to view this
          portal section. All role and organization permissions are strictly enforced by the server.
        </p>
        <Link
          to={home}
          className="mt-6 inline-flex items-center justify-center rounded-xl bg-navy-900 px-5 py-2.5 text-sm font-semibold text-white hover:bg-navy-800"
        >
          Return to My Portal
        </Link>
      </div>
    </div>
  );
}
