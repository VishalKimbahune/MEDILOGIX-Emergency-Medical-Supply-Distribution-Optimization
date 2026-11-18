import React, { useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import {
  Activity,
  BarChart3,
  Boxes,
  Building2,
  ClipboardList,
  Cpu,
  Flame,
  LayoutDashboard,
  Menu,
  Route as RouteIcon,
  Settings,
  Warehouse,
  X,
} from 'lucide-react';
import { useApiHealth } from '../hooks/useApiHealth';

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/warehouses', label: 'Warehouses', icon: Warehouse },
  { to: '/hospitals', label: 'Hospitals', icon: Building2 },
  { to: '/inventory', label: 'Inventory', icon: Boxes },
  { to: '/demands', label: 'Demand Requests', icon: ClipboardList },
  { to: '/optimization', label: 'Optimization', icon: Cpu },
  { to: '/routes', label: 'Delivery Routes', icon: RouteIcon },
  { to: '/scenarios', label: 'Scenario Simulator', icon: Flame },
  { to: '/analytics', label: 'Analytics & Reports', icon: BarChart3 },
  { to: '/settings', label: 'Settings', icon: Settings },
];

export default function MainLayout() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const { health, status } = useApiHealth();

  const statusPill =
    status === 'online'
      ? { dot: 'bg-emerald-500', text: 'API Connected', box: 'bg-emerald-50 text-emerald-800 border-emerald-200' }
      : status === 'checking'
      ? { dot: 'bg-amber-400', text: 'Checking API...', box: 'bg-amber-50 text-amber-800 border-amber-200' }
      : { dot: 'bg-red-500', text: 'API Offline', box: 'bg-red-50 text-red-800 border-red-200' };

  return (
    <div className="flex min-h-screen bg-slate-50">
      {/* Mobile Overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-30 bg-slate-900/60 lg:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Dark Navy Enterprise Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-64 flex-col bg-navy-900 text-slate-200 transition-transform duration-200 lg:static lg:translate-x-0 ${
          mobileOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex h-16 items-center justify-between border-b border-white/10 px-5">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-teal-500/20 text-teal-400 ring-1 ring-teal-400/30">
              <Activity className="h-5 w-5" />
            </div>
            <div>
              <span className="block text-base font-bold tracking-wide text-white">
                MEDILOGIX
              </span>
              <span className="block text-[10px] font-medium uppercase tracking-wider text-teal-300/80">
                OR Decision Support
              </span>
            </div>
          </div>
          <button
            type="button"
            className="rounded p-1 text-slate-400 hover:text-white lg:hidden"
            onClick={() => setMobileOpen(false)}
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
          {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              onClick={() => setMobileOpen(false)}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition ${
                  isActive
                    ? 'bg-teal-600 text-white shadow-sm'
                    : 'text-slate-300 hover:bg-navy-800 hover:text-white'
                }`
              }
            >
              <Icon className="h-4 w-4 shrink-0" />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-white/10 p-4 text-[11px] text-slate-400">
          <p className="font-semibold text-slate-200">Simulation Scope</p>
          <p className="mt-0.5">
            {health?.geographical_scope?.region_name || 'Pune Urban & Pimpri-Chinchwad'}
          </p>
          <p className="mt-1.5 text-[10px] text-slate-400/80">
            Synthetic operational data &bull; Fictional hubs
          </p>
        </div>
      </aside>

      {/* Main Content Shell */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-slate-200 bg-white px-4 sm:px-6">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setMobileOpen(true)}
              className="rounded-lg border border-slate-200 p-2 text-slate-600 hover:bg-slate-50 lg:hidden"
            >
              <Menu className="h-5 w-5" />
            </button>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-teal-700">
                Emergency Medical Supply Distribution Platform
              </p>
              <p className="text-xs text-slate-500">
                Operations Research &bull; Supply Chain Management (Pune, Maharashtra)
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div
              className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold ${statusPill.box}`}
            >
              <span className={`h-2 w-2 rounded-full ${statusPill.dot}`} />
              <span>{statusPill.text}</span>
            </div>
          </div>
        </header>

        <main className="flex-1 p-4 sm:p-6 lg:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
