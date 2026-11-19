import React from 'react';
import { Activity, ShieldCheck, Truck, Warehouse, Building2 } from 'lucide-react';

export default function AuthLayout({ title, subtitle, children }) {
  return (
    <div className="flex min-h-screen bg-slate-50">
      {/* Left Enterprise Brand Panel */}
      <div className="relative hidden w-[44%] flex-col justify-between overflow-hidden bg-navy-900 p-10 text-white lg:flex">
        <div
          className="pointer-events-none absolute inset-0 opacity-20"
          style={{
            backgroundImage:
              'radial-gradient(circle at 20% 20%, #0284c7 0%, transparent 45%), radial-gradient(circle at 80% 80%, #0d9488 0%, transparent 45%)',
          }}
        />
        <div className="relative z-10">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-teal-500/20 text-teal-300 ring-1 ring-teal-400/30">
              <Activity className="h-6 w-6" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-wide text-white">MEDILOGIX</h1>
              <p className="text-xs font-medium uppercase tracking-widest text-teal-300">
                Emergency Healthcare Supply Platform
              </p>
            </div>
          </div>

          <div className="mt-12 max-w-md">
            <h2 className="text-3xl font-bold leading-tight text-white">
              Intelligent Medical Supply Distribution &amp; Operations Research
            </h2>
            <p className="mt-4 text-sm leading-relaxed text-slate-300">
              Coordinating emergency medical supply allocation, priority-aware shortage protection,
              multi-depot vehicle routing on Pune OpenStreetMap corridors, and traceable last-mile
              hospital delivery across four secure role-based portals.
            </p>
          </div>

          <div className="mt-10 grid grid-cols-2 gap-4">
            <div className="rounded-xl border border-white/10 bg-white/5 p-4">
              <ShieldCheck className="h-5 w-5 text-sky-400" />
              <p className="mt-2 text-xs font-semibold text-white">Admin Command</p>
              <p className="mt-1 text-[11px] text-slate-400">
                LP &amp; Lexicographic OR, VRP dispatch, disaster simulation &amp; governance
              </p>
            </div>
            <div className="rounded-xl border border-white/10 bg-white/5 p-4">
              <Building2 className="h-5 w-5 text-teal-400" />
              <p className="mt-2 text-xs font-semibold text-white">Hospital Portal</p>
              <p className="mt-1 text-[11px] text-slate-400">
                Emergency orders, priority justification &amp; live delivery timelines
              </p>
            </div>
            <div className="rounded-xl border border-white/10 bg-white/5 p-4">
              <Warehouse className="h-5 w-5 text-amber-400" />
              <p className="mt-2 text-xs font-semibold text-white">Warehouse Portal</p>
              <p className="mt-1 text-[11px] text-slate-400">
                Controlled stock movements, depot status &amp; shipment preparation
              </p>
            </div>
            <div className="rounded-xl border border-white/10 bg-white/5 p-4">
              <Truck className="h-5 w-5 text-emerald-400" />
              <p className="mt-2 text-xs font-semibold text-white">Delivery Portal</p>
              <p className="mt-1 text-[11px] text-slate-400">
                Assigned OSM road routes, stop tracking &amp; delivery confirmation
              </p>
            </div>
          </div>
        </div>

        <div className="relative z-10 border-t border-white/10 pt-5 text-[11px] text-slate-400">
          Pune &amp; Pimpri-Chinchwad Academic Simulation &bull; Road geometry &copy; OpenStreetMap
          contributors (ODbL 1.0)
        </div>
      </div>

      {/* Right Auth Card Column */}
      <div className="flex flex-1 flex-col justify-between px-4 py-8 sm:px-8 lg:px-14">
        <div className="flex items-center gap-2.5 lg:hidden">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-navy-900 text-teal-400">
            <Activity className="h-5 w-5" />
          </div>
          <div>
            <span className="block text-base font-bold text-slate-900">MEDILOGIX</span>
            <span className="block text-[10px] font-semibold uppercase tracking-wider text-teal-700">
              Healthcare Supply Optimization
            </span>
          </div>
        </div>

        <div className="mx-auto my-auto w-full max-w-lg py-6">
          <div className="rounded-2xl border border-slate-200 bg-white p-7 shadow-sm sm:p-8">
            <h2 className="text-2xl font-bold tracking-tight text-slate-900">{title}</h2>
            {subtitle && <p className="mt-1.5 text-sm text-slate-500">{subtitle}</p>}
            <div className="mt-6">{children}</div>
          </div>
        </div>

        <p className="text-center text-[11px] text-slate-400">
          MEDILOGIX Academic Decision-Support Prototype &bull; Role-Based Access Control Enabled
        </p>
      </div>
    </div>
  );
}
