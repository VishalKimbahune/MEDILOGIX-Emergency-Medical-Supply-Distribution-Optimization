import React, { useEffect, useState } from 'react';
import { Cpu, Database, Globe, ShieldCheck } from 'lucide-react';
import PageHeader from '../components/common/PageHeader';
import StatusBadge from '../components/common/StatusBadge';
import { useApiHealth } from '../hooks/useApiHealth';
import { routeService } from '../services/routeService';
import { formatNumber } from '../utils/formatters';

export default function Settings() {
  const { health, status } = useApiHealth();
  const [roadNet, setRoadNet] = useState(null);

  useEffect(() => {
    routeService
      .getRoadNetworkStatus()
      .then(setRoadNet)
      .catch(() => setRoadNet(null));
  }, []);

  const bounds = health?.geographical_scope?.bounds;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Platform Settings & System Configuration"
        badge="Environment & Solvers"
        description="Runtime API connectivity, configurable Pune & Pimpri-Chinchwad geographical bounds, Operations Research solver stack, and OpenStreetMap road-network cache status."
      />

      {/* Runtime Environment Status */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-center gap-2">
          <Database className="h-4 w-4 text-teal-600" />
          <h2 className="text-sm font-bold text-slate-900">Runtime Environment &amp; API Status</h2>
        </div>
        <dl className="mt-4 grid grid-cols-1 gap-4 text-xs sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-lg bg-slate-50 p-3.5">
            <dt className="font-semibold text-slate-500">API Base URL</dt>
            <dd className="mt-1 break-all font-mono text-slate-900">
              {import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api'}
            </dd>
          </div>
          <div className="rounded-lg bg-slate-50 p-3.5">
            <dt className="font-semibold text-slate-500">Backend Connectivity</dt>
            <dd className="mt-1">
              <StatusBadge
                status={status === 'online' ? 'active' : 'inactive'}
                label={status === 'online' ? 'Online' : status}
              />
            </dd>
          </div>
          <div className="rounded-lg bg-slate-50 p-3.5">
            <dt className="font-semibold text-slate-500">Database Connected</dt>
            <dd className="mt-1 font-semibold text-slate-900">
              {health ? (health.database_connected ? 'Connected (SQLAlchemy)' : 'Disconnected') : 'Unknown'}
            </dd>
          </div>
          <div className="rounded-lg bg-slate-50 p-3.5">
            <dt className="font-semibold text-slate-500">Deployment Mode</dt>
            <dd className="mt-1 capitalize font-semibold text-slate-900">
              {health?.environment || 'development'}
            </dd>
          </div>
        </dl>
      </div>

      {/* Geographical & OSM Road Network Configuration */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Globe className="h-4 w-4 text-teal-600" />
              <h2 className="text-sm font-bold text-slate-900">
                Geographical Scope &amp; OSM Road Cache
              </h2>
            </div>
            <StatusBadge
              status={roadNet?.osm_available ? 'active' : 'inactive'}
              label={roadNet?.osm_available ? 'OSM Cached' : 'Synthetic Fallback'}
            />
          </div>
          <dl className="grid grid-cols-2 gap-3 text-xs">
            <div className="rounded-lg bg-slate-50 p-3">
              <dt className="font-semibold text-slate-500">Configured Region</dt>
              <dd className="mt-1 font-semibold text-slate-900">
                {health?.geographical_scope?.region_name || 'Pune Urban & Pimpri-Chinchwad'}
              </dd>
            </div>
            <div className="rounded-lg bg-slate-50 p-3">
              <dt className="font-semibold text-slate-500">Bounding Box</dt>
              <dd className="mt-1 font-mono text-[11px] text-slate-800">
                {bounds
                  ? `Lat ${bounds.min_lat}–${bounds.max_lat}, Lon ${bounds.min_lon}–${bounds.max_lon}`
                  : '18.40–18.70, 73.70–74.05'}
              </dd>
            </div>
            <div className="rounded-lg bg-slate-50 p-3">
              <dt className="font-semibold text-slate-500">Cached OSM Graph</dt>
              <dd className="mt-1 font-semibold text-slate-900">
                {roadNet?.osm_available
                  ? `${formatNumber(roadNet.node_count)} nodes / ${formatNumber(roadNet.edge_count)} edges`
                  : 'Not cached locally'}
              </dd>
            </div>
            <div className="rounded-lg bg-slate-50 p-3">
              <dt className="font-semibold text-slate-500">Data Attribution</dt>
              <dd className="mt-1 text-slate-800">
                &copy; OpenStreetMap contributors (ODbL 1.0)
              </dd>
            </div>
          </dl>
          <p className="text-[11px] text-slate-500">
            Configure bounds via backend environment variables (<code>GEO_MIN_LAT</code>,{' '}
            <code>GEO_MAX_LAT</code>, <code>GEO_MIN_LON</code>, <code>GEO_MAX_LON</code>) and
            synchronize OSM road geometry under <strong>Delivery Routes &rarr; Road Network &amp; Corridors</strong>.
          </p>
        </div>

        {/* Operations Research Solver Stack */}
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm space-y-3">
          <div className="flex items-center gap-2">
            <Cpu className="h-4 w-4 text-teal-600" />
            <h2 className="text-sm font-bold text-slate-900">Operations Research Solver Stack</h2>
          </div>
          <ul className="space-y-2.5 text-xs text-slate-700">
            <li className="rounded-lg bg-slate-50 p-3">
              <strong className="text-slate-900">Supply Allocation (Phase 3):</strong> PuLP + CBC
              (COIN-OR Branch and Cut) — Multi-Commodity Transportation LP &amp; 4-Stage Sequential
              Lexicographic Priority LP (Critical &rarr; High &rarr; Normal &rarr; Transport Cost).
            </li>
            <li className="rounded-lg bg-slate-50 p-3">
              <strong className="text-slate-900">Vehicle Routing (Phase 4–5):</strong> Google
              OR-Tools Multi-Depot CVRP (1D weight capacity in kg, multi-wave trips, split-load
              conservation, Minimum Road Distance or Minimum Estimated Travel Time).
            </li>
            <li className="rounded-lg bg-slate-50 p-3">
              <strong className="text-slate-900">Road Network Graph (Phase 5):</strong> NetworkX
              Directed <code>MultiDiGraph</code> with one-way enforcement, HGV/delivery access
              filtering, OSM <code>way_id</code> road closures, and offline synthetic fallback.
            </li>
          </ul>
        </div>
      </div>

      {/* Academic & Data Integrity Notice */}
      <div className="rounded-xl border border-teal-200 bg-teal-50/70 p-5 text-xs text-slate-700">
        <div className="flex items-start gap-2.5">
          <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-teal-700" />
          <div className="space-y-1">
            <p className="font-bold text-slate-900">Academic &amp; Modeling Integrity Statement</p>
            <p>
              All warehouses are modeled as fictional simulation hubs, and hospital demands,
              inventory quantities, and fleet profiles are synthetic datasets seeded reproducibly
              (<code>RANDOM_SEED = 42</code>). Road geometry reflects real Pune &amp; Pimpri-Chinchwad
              OpenStreetMap streets (<code>&copy; OpenStreetMap contributors, ODbL 1.0</code>), while
              travel times are estimated using assumed road-class speed profiles and do{' '}
              <strong>not</strong> represent live traffic, real-time congestion, or GPS tracking.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
