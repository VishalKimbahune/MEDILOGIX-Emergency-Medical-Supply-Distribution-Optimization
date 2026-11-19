import React, { useEffect, useRef, useState } from 'react';
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import {
  Activity,
  BarChart3,
  Bell,
  Boxes,
  Building2,
  CheckCheck,
  ClipboardList,
  Cpu,
  FileClock,
  Flame,
  History,
  LayoutDashboard,
  LogOut,
  Menu,
  PackageCheck,
  PlusCircle,
  Route as RouteIcon,
  Settings,
  ShieldCheck,
  Truck,
  UserCircle2,
  Users,
  Warehouse,
  X,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useApiHealth } from '../hooks/useApiHealth';
import {
  fetchNotifications,
  fetchUnreadNotificationCount,
  markAllNotificationsRead,
  markNotificationRead,
} from '../services/notificationService';

const NAV_BY_ROLE = {
  admin: [
    {
      section: 'Command Center',
      items: [
        { to: '/admin/dashboard', label: 'Overview', icon: LayoutDashboard },
        { to: '/admin/demands', label: 'Orders & Demands', icon: ClipboardList },
        { to: '/admin/optimization', label: 'Optimization Engine', icon: Cpu },
        { to: '/admin/routes', label: 'Routes & Dispatch', icon: RouteIcon },
        { to: '/admin/scenarios', label: 'Disaster Simulator', icon: Flame },
        { to: '/admin/analytics', label: 'Analytics & Reports', icon: BarChart3 },
      ],
    },
    {
      section: 'Network & Fleet',
      items: [
        { to: '/admin/warehouses', label: 'Warehouses', icon: Warehouse },
        { to: '/admin/hospitals', label: 'Hospitals', icon: Building2 },
        { to: '/admin/inventory', label: 'Inventory', icon: Boxes },
        { to: '/admin/vehicles', label: 'Fleet & Drivers', icon: Truck },
      ],
    },
    {
      section: 'Governance',
      items: [
        { to: '/admin/users', label: 'Users & Approvals', icon: Users },
        { to: '/admin/audit-logs', label: 'Audit Logs', icon: FileClock },
        { to: '/admin/notifications', label: 'Notifications', icon: Bell },
        { to: '/admin/settings', label: 'Settings', icon: Settings },
      ],
    },
  ],
  hospital: [
    {
      section: 'Hospital Portal',
      items: [
        { to: '/hospital/dashboard', label: 'Dashboard', icon: LayoutDashboard },
        { to: '/hospital/orders/new', label: 'Create Supply Order', icon: PlusCircle },
        { to: '/hospital/orders', label: 'Orders & Tracking', icon: ClipboardList },
        { to: '/hospital/notifications', label: 'Notifications', icon: Bell },
        { to: '/hospital/profile', label: 'Hospital Profile', icon: Building2 },
      ],
    },
  ],
  warehouse: [
    {
      section: 'Warehouse Portal',
      items: [
        { to: '/warehouse/dashboard', label: 'Dashboard', icon: LayoutDashboard },
        { to: '/warehouse/inventory', label: 'Stock & Movements', icon: Boxes },
        { to: '/warehouse/shipments', label: 'Allocations & Dispatch', icon: PackageCheck },
        { to: '/warehouse/notifications', label: 'Notifications', icon: Bell },
        { to: '/warehouse/profile', label: 'Warehouse Status', icon: Warehouse },
      ],
    },
  ],
  delivery: [
    {
      section: 'Delivery Portal',
      items: [
        { to: '/delivery/dashboard', label: 'Driver Dashboard', icon: LayoutDashboard },
        { to: '/delivery/assignments', label: 'Active Routes & Map', icon: Truck },
        { to: '/delivery/history', label: 'Delivery History', icon: History },
        { to: '/delivery/notifications', label: 'Notifications', icon: Bell },
        { to: '/delivery/profile', label: 'Driver Profile', icon: UserCircle2 },
      ],
    },
  ],
};

const ROLE_META = {
  admin: { label: 'Administrator', accent: 'bg-sky-500/20 text-sky-300 ring-sky-400/30', portal: 'Admin Command' },
  hospital: { label: 'Hospital', accent: 'bg-teal-500/20 text-teal-300 ring-teal-400/30', portal: 'Hospital Portal' },
  warehouse: { label: 'Warehouse', accent: 'bg-amber-500/20 text-amber-300 ring-amber-400/30', portal: 'Warehouse Portal' },
  delivery: { label: 'Delivery', accent: 'bg-emerald-500/20 text-emerald-300 ring-emerald-400/30', portal: 'Delivery Portal' },
};

export default function MainLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const { health, status } = useApiHealth();

  const [mobileOpen, setMobileOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const [recentNotifs, setRecentNotifs] = useState([]);
  const notifRef = useRef(null);

  const role = user?.role || 'hospital';
  const navGroups = NAV_BY_ROLE[role] || [];
  const meta = ROLE_META[role] || ROLE_META.hospital;

  useEffect(() => {
    if (!user) return;
    let active = true;
    const loadCount = () => {
      fetchUnreadNotificationCount()
        .then((res) => {
          if (active) setUnreadCount(res?.unread_count || 0);
        })
        .catch(() => {});
    };
    loadCount();
    const timer = setInterval(loadCount, 30000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [user, location.pathname]);

  useEffect(() => {
    function handleOutside(e) {
      if (notifRef.current && !notifRef.current.contains(e.target)) {
        setNotifOpen(false);
      }
    }
    document.addEventListener('mousedown', handleOutside);
    return () => document.removeEventListener('mousedown', handleOutside);
  }, []);

  async function toggleNotifDropdown() {
    const next = !notifOpen;
    setNotifOpen(next);
    if (next) {
      try {
        const list = await fetchNotifications({ limit: 8 });
        setRecentNotifs(list || []);
      } catch {
        setRecentNotifs([]);
      }
    }
  }

  async function handleReadOne(id) {
    try {
      await markNotificationRead(id);
      setRecentNotifs((prev) => prev.map((n) => (n.id === id ? { ...n, is_read: true } : n)));
      setUnreadCount((c) => Math.max(0, c - 1));
    } catch {
      // ignore
    }
  }

  async function handleReadAll() {
    try {
      await markAllNotificationsRead();
      setRecentNotifs((prev) => prev.map((n) => ({ ...n, is_read: true })));
      setUnreadCount(0);
    } catch {
      // ignore
    }
  }

  async function handleSignOut() {
    await logout();
    navigate('/login', { replace: true });
  }

  const orgSubtitle =
    role === 'hospital' && user?.associated_hospital_name
      ? `${user.associated_hospital_code} • ${user.associated_hospital_name}`
      : role === 'warehouse' && user?.associated_warehouse_name
      ? `${user.associated_warehouse_code} • ${user.associated_warehouse_name}`
      : role === 'delivery' && user?.assigned_vehicle_codes?.length
      ? `Assigned: ${user.assigned_vehicle_codes.join(', ')}`
      : health?.geographical_scope?.region_name || 'Pune & Pimpri-Chinchwad';

  const statusPill =
    status === 'online'
      ? { dot: 'bg-emerald-500', text: 'API Online', box: 'bg-emerald-50 text-emerald-800 border-emerald-200' }
      : status === 'checking'
      ? { dot: 'bg-amber-400', text: 'Checking...', box: 'bg-amber-50 text-amber-800 border-amber-200' }
      : { dot: 'bg-red-500', text: 'API Offline', box: 'bg-red-50 text-red-800 border-red-200' };

  return (
    <div className="flex min-h-screen bg-slate-50">
      {mobileOpen && (
        <div
          className="fixed inset-0 z-30 bg-slate-900/60 lg:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Enterprise Navy Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-64 flex-col bg-navy-900 text-slate-200 transition-transform duration-200 lg:static lg:translate-x-0 ${
          mobileOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex h-16 items-center justify-between border-b border-white/10 px-5">
          <div className="flex items-center gap-2.5">
            <div className={`flex h-9 w-9 items-center justify-center rounded-lg ring-1 ${meta.accent}`}>
              <Activity className="h-5 w-5" />
            </div>
            <div>
              <span className="block text-base font-bold tracking-wide text-white">MEDILOGIX</span>
              <span className="block text-[10px] font-semibold uppercase tracking-wider text-teal-300/90">
                {meta.portal}
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

        <nav className="flex-1 space-y-5 overflow-y-auto px-3 py-4">
          {navGroups.map((group) => (
            <div key={group.section}>
              <p className="mb-1.5 px-3 text-[10px] font-bold uppercase tracking-widest text-slate-400">
                {group.section}
              </p>
              <div className="space-y-1">
                {group.items.map(({ to, label, icon: Icon }) => (
                  <NavLink
                    key={to}
                    to={to}
                    onClick={() => setMobileOpen(false)}
                    className={({ isActive }) =>
                      `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${
                        isActive
                          ? 'bg-teal-600 text-white shadow-sm'
                          : 'text-slate-300 hover:bg-navy-800 hover:text-white'
                      }`
                    }
                  >
                    <Icon className="h-4 w-4 shrink-0" />
                    <span className="truncate">{label}</span>
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </nav>

        <div className="border-t border-white/10 p-4">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-white/10 text-xs font-bold text-white">
              {(user?.full_name || 'U').slice(0, 2).toUpperCase()}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-xs font-semibold text-white">{user?.full_name}</p>
              <p className="truncate text-[10px] text-slate-400">{user?.email}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={handleSignOut}
            className="mt-3 flex w-full items-center justify-center gap-2 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-semibold text-slate-200 transition hover:bg-red-500/20 hover:text-red-200"
          >
            <LogOut className="h-3.5 w-3.5" />
            <span>Sign Out</span>
          </button>
        </div>
      </aside>

      {/* Main Content Shell */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-slate-200 bg-white px-4 sm:px-6">
          <div className="flex min-w-0 items-center gap-3">
            <button
              type="button"
              onClick={() => setMobileOpen(true)}
              className="rounded-lg border border-slate-200 p-2 text-slate-600 hover:bg-slate-50 lg:hidden"
            >
              <Menu className="h-5 w-5" />
            </button>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="inline-flex items-center gap-1 rounded-full bg-navy-900 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-white">
                  <ShieldCheck className="h-3 w-3 text-teal-400" />
                  {meta.label}
                </span>
                <p className="hidden truncate text-xs font-semibold text-slate-700 sm:block">
                  {orgSubtitle}
                </p>
              </div>
              <p className="truncate text-[11px] text-slate-500 sm:hidden">{orgSubtitle}</p>
            </div>
          </div>

          <div className="flex items-center gap-2.5 sm:gap-3">
            <div
              className={`hidden items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold sm:inline-flex ${statusPill.box}`}
            >
              <span className={`h-2 w-2 rounded-full ${statusPill.dot}`} />
              <span>{statusPill.text}</span>
            </div>

            {/* Notification Bell */}
            <div className="relative" ref={notifRef}>
              <button
                type="button"
                onClick={toggleNotifDropdown}
                className="relative flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
                aria-label="Notifications"
              >
                <Bell className="h-4 w-4" />
                {unreadCount > 0 && (
                  <span className="absolute -right-1 -top-1 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-red-600 px-1 text-[10px] font-bold text-white">
                    {unreadCount > 99 ? '99+' : unreadCount}
                  </span>
                )}
              </button>

              {notifOpen && (
                <div className="absolute right-0 mt-2 w-80 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xl sm:w-96">
                  <div className="flex items-center justify-between border-b border-slate-100 px-4 py-2.5">
                    <span className="text-xs font-bold uppercase tracking-wider text-slate-700">
                      Notifications ({unreadCount} unread)
                    </span>
                    {unreadCount > 0 && (
                      <button
                        type="button"
                        onClick={handleReadAll}
                        className="inline-flex items-center gap-1 text-[11px] font-semibold text-teal-700 hover:underline"
                      >
                        <CheckCheck className="h-3.5 w-3.5" />
                        Mark all read
                      </button>
                    )}
                  </div>
                  <div className="max-h-80 divide-y divide-slate-100 overflow-y-auto">
                    {recentNotifs.length === 0 ? (
                      <p className="px-4 py-6 text-center text-xs text-slate-400">
                        No notifications yet.
                      </p>
                    ) : (
                      recentNotifs.map((n) => (
                        <div
                          key={n.id}
                          onClick={() => !n.is_read && handleReadOne(n.id)}
                          className={`cursor-pointer px-4 py-3 transition hover:bg-slate-50 ${
                            n.is_read ? 'bg-white' : 'bg-sky-50/50'
                          }`}
                        >
                          <div className="flex items-start justify-between gap-2">
                            <p className="text-xs font-semibold text-slate-800">{n.title}</p>
                            {!n.is_read && (
                              <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-sky-600" />
                            )}
                          </div>
                          <p className="mt-0.5 text-[11px] leading-relaxed text-slate-600">
                            {n.message}
                          </p>
                        </div>
                      ))
                    )}
                  </div>
                  <div className="border-t border-slate-100 bg-slate-50 px-4 py-2 text-center">
                    <Link
                      to={`/${role}/notifications`}
                      onClick={() => setNotifOpen(false)}
                      className="text-xs font-semibold text-sky-700 hover:underline"
                    >
                      View all notifications
                    </Link>
                  </div>
                </div>
              )}
            </div>
          </div>
        </header>

        <main className="flex-1 p-4 sm:p-6 lg:p-8">
          <Outlet />
        </main>

        <footer className="border-t border-slate-200 bg-white px-4 py-2.5 text-[11px] text-slate-500 sm:px-6">
          MEDILOGIX uses illustrative operational data for academic demonstration. Road geometry is
          sourced from OpenStreetMap (<strong>&copy; OpenStreetMap contributors, ODbL 1.0</strong>),
          while travel times are estimated using assumed road-class speeds (not live traffic or GPS).
          This platform is a decision-support prototype and is not connected to live hospital
          inventory or emergency dispatch systems.
        </footer>
      </div>
    </div>
  );
}
