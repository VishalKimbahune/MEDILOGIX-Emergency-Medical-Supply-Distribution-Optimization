import React, { useMemo, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  Compass,
  Database,
  Globe,
  RefreshCw,
  Route as RouteIcon,
} from 'lucide-react';
import StatusBadge from '../common/StatusBadge';
import { useToast } from '../common/ToastContext';
import { routeService } from '../../services/routeService';
import { extractApiError, formatNumber } from '../../utils/formatters';

export default function RoadNetworkPanel({
  roadNetworkStatus,
  onStatusUpdated,
  warehouses = [],
  hospitals = [],
}) {
  const toast = useToast();

  // Manual OSM synchronization state (non-blocking)
  const [syncing, setSyncing] = useState(false);
  const [forceRefresh, setForceRefresh] = useState(false);
  const [syncMessage, setSyncMessage] = useState(null);

  // Interactive directed shortest-path lookup state
  const facilities = useMemo(() => {
    const items = [];
    warehouses.forEach((w) =>
      items.push({ code: w.code, label: `${w.code} — ${w.name} (Warehouse)` })
    );
    hospitals.forEach((h) =>
      items.push({ code: h.code, label: `${h.code} — ${h.name} (Hospital)` })
    );
    return items;
  }, [warehouses, hospitals]);

  const [sourceCode, setSourceCode] = useState('WH-01');
  const [targetCode, setTargetCode] = useState('HOSP-01');
  const [weightMetric, setWeightMetric] = useState('distance_km');
  const [closedWaysText, setClosedWaysText] = useState('');
  const [queryingPath, setQueryingPath] = useState(false);
  const [pathResult, setPathResult] = useState(null);
  const [pathError, setPathError] = useState(null);

  async function handleSyncOsm() {
    setSyncing(true);
    setSyncMessage(null);
    try {
      const updated = await routeService.syncRoadNetwork(forceRefresh);
      if (onStatusUpdated) onStatusUpdated(updated);

      const action = updated.sync_action;
      if (action === 'downloaded_and_cached') {
        setSyncMessage({
          type: 'success',
          text: `Downloaded and cached ${formatNumber(updated.node_count)} nodes and ${formatNumber(
            updated.edge_count
          )} directed road segments from Overpass API.`,
        });
        toast.success('OSM network synchronized', 'Local Pune road graph cache updated.');
      } else if (action === 'reused_existing_cache') {
        setSyncMessage({
          type: 'info',
          text: `Existing local cache verified and reused (${formatNumber(
            updated.node_count
          )} nodes / ${formatNumber(
            updated.edge_count
          )} segments). Enable "Force re-download" to refresh from Overpass.`,
        });
        toast.info('Local OSM cache reused', 'No Overpass API call was needed.');
      } else {
        setSyncMessage({
          type: 'warning',
          text: `Overpass API synchronization failed (${
            updated.sync_error || 'endpoint unavailable or timed out'
          }). Active source: ${
            updated.osm_available ? 'existing local OSM cache' : 'synthetic corridor fallback'
          }.`,
        });
        toast.warning('OSM sync fallback', 'Overpass unavailable; application continues normally.');
      }
    } catch (err) {
      const msg = extractApiError(err, 'Synchronization request timed out or backend unreachable.');
      setSyncMessage({ type: 'error', text: msg });
      toast.error('Sync failed', msg);
    } finally {
      setSyncing(false);
    }
  }

  async function handleShortestPathLookup(e) {
    e.preventDefault();
    if (!sourceCode || !targetCode || sourceCode === targetCode) {
      setPathError('Select two distinct facilities to compute a directed shortest path.');
      return;
    }
    const closedWayIds = closedWaysText
      .split(/[,\s]+/)
      .map((t) => t.trim())
      .filter(Boolean)
      .map((t) => Number(t))
      .filter((n) => Number.isInteger(n) && n > 0);

    setQueryingPath(true);
    setPathError(null);
    try {
      const result = await routeService.osmShortestPath({
        source_code: sourceCode,
        target_code: targetCode,
        weight_metric: weightMetric,
        closed_way_ids: closedWayIds,
        allow_synthetic_fallback: true,
      });
      setPathResult(result);
    } catch (err) {
      setPathError(extractApiError(err, 'Unable to compute shortest path.'));
      setPathResult(null);
    } finally {
      setQueryingPath(false);
    }
  }

  const mappings = roadNetworkStatus?.facility_mappings || [];
  const connectedCount = mappings.filter((m) => m.is_connected).length;
  const disconnectedCount = (roadNetworkStatus?.disconnected_facilities || []).length;
  const connectivityPct =
    roadNetworkStatus?.node_count > 0
      ? ((roadNetworkStatus.largest_scc_node_count / roadNetworkStatus.node_count) * 100).toFixed(1)
      : '0.0';
  const lastSyncIso = roadNetworkStatus?.metadata?.generated_at_utc;

  return (
    <div className="space-y-6">
      {/* OSM Road Network Status & Manual Synchronization Card */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-100 pb-4">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <Globe className="h-4 w-4 text-teal-600" />
              <h3 className="text-sm font-bold text-slate-900">
                OpenStreetMap Road Network Management (Pune &amp; PCMC)
              </h3>
              <StatusBadge
                status={roadNetworkStatus?.osm_available ? 'active' : 'inactive'}
                label={
                  roadNetworkStatus?.osm_available ? 'OSM Cache Active' : 'Synthetic Fallback Active'
                }
              />
            </div>
            <p className="mt-1 text-xs text-slate-500">
              {roadNetworkStatus?.note ||
                'Inspect cached directed road-network connectivity, trigger polite Overpass synchronization, or test directed shortest paths.'}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <label className="inline-flex cursor-pointer items-center gap-1.5 text-xs text-slate-600">
              <input
                type="checkbox"
                checked={forceRefresh}
                onChange={(e) => setForceRefresh(e.target.checked)}
                className="rounded border-slate-300 text-teal-600 focus:ring-teal-600"
              />
              Force Overpass re-download
            </label>
            <button
              type="button"
              disabled={syncing}
              onClick={handleSyncOsm}
              className="inline-flex items-center gap-1.5 rounded-lg bg-navy-900 px-4 py-2 text-xs font-semibold text-white hover:bg-navy-800 disabled:opacity-50"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${syncing ? 'animate-spin' : ''}`} />
              {syncing ? 'Synchronizing OSM...' : 'Synchronize OSM Network'}
            </button>
          </div>
        </div>

        {syncMessage && (
          <div
            className={`rounded-lg border px-3.5 py-2.5 text-xs ${
              syncMessage.type === 'success'
                ? 'border-emerald-200 bg-emerald-50 text-emerald-900'
                : syncMessage.type === 'warning'
                ? 'border-amber-200 bg-amber-50 text-amber-900'
                : syncMessage.type === 'error'
                ? 'border-red-200 bg-red-50 text-red-900'
                : 'border-sky-200 bg-sky-50 text-sky-900'
            }`}
          >
            {syncMessage.text}
          </div>
        )}

        {/* Graph & Connectivity Metrics Grid */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <div className="rounded-lg border border-slate-100 bg-slate-50 p-3">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
              Active Source
            </p>
            <p className="mt-1 text-xs font-bold text-slate-900">
              {roadNetworkStatus?.osm_available ? 'OSM Directed Graph' : 'Synthetic Fallback'}
            </p>
          </div>
          <div className="rounded-lg border border-slate-100 bg-slate-50 p-3">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
              Road Nodes
            </p>
            <p className="mt-1 text-sm font-bold text-slate-900">
              {formatNumber(roadNetworkStatus?.node_count || 0)}
            </p>
          </div>
          <div className="rounded-lg border border-slate-100 bg-slate-50 p-3">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
              Directed Edges
            </p>
            <p className="mt-1 text-sm font-bold text-slate-900">
              {formatNumber(roadNetworkStatus?.edge_count || 0)}
            </p>
            <p className="text-[10px] text-slate-500">
              {formatNumber(roadNetworkStatus?.oneway_edge_count || 0)} one-way
            </p>
          </div>
          <div className="rounded-lg border border-slate-100 bg-slate-50 p-3">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
              Main SCC Connectivity
            </p>
            <p className="mt-1 text-sm font-bold text-teal-800">{connectivityPct}%</p>
            <p className="text-[10px] text-slate-500">
              {formatNumber(roadNetworkStatus?.largest_scc_node_count || 0)} nodes
            </p>
          </div>
          <div className="rounded-lg border border-slate-100 bg-slate-50 p-3">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
              Facilities Snapped
            </p>
            <p className="mt-1 text-sm font-bold text-emerald-700">
              {connectedCount} / {mappings.length}
            </p>
            <p className="text-[10px] text-slate-500">
              {disconnectedCount} disconnected
            </p>
          </div>
          <div className="rounded-lg border border-slate-100 bg-slate-50 p-3">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
              Last Sync (UTC)
            </p>
            <p className="mt-1 text-[11px] font-semibold text-slate-800">
              {lastSyncIso ? new Date(lastSyncIso).toLocaleString() : 'Not cached yet'}
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-slate-500">
          <span className="inline-flex items-center gap-1.5">
            <Database className="h-3.5 w-3.5 text-slate-400" />
            Cache: <code className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px]">{roadNetworkStatus?.cache_file || 'data/processed/pune_osm_road_graph.json'}</code>
          </span>
          <span>
            Attribution: <strong>{roadNetworkStatus?.attribution || '© OpenStreetMap contributors (ODbL 1.0)'}</strong>
          </span>
        </div>

        {/* Facility Snapping Pills */}
        {mappings.length > 0 && (
          <div className="border-t border-slate-100 pt-3">
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
              Active Facility Road-Network Snapping Status
            </p>
            <div className="flex flex-wrap gap-2">
              {mappings.map((m) => (
                <span
                  key={m.facility_code}
                  className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-[11px] font-medium ${
                    m.is_connected
                      ? 'border-emerald-200 bg-emerald-50/70 text-emerald-900'
                      : 'border-red-200 bg-red-50 text-red-800'
                  }`}
                >
                  {m.is_connected ? (
                    <CheckCircle2 className="h-3 w-3 text-emerald-600" />
                  ) : (
                    <AlertTriangle className="h-3 w-3 text-red-600" />
                  )}
                  <strong>{m.facility_code}</strong>
                  <span className="text-[10px] opacity-80">
                    {m.snap_distance_km !== null ? `${m.snap_distance_km} km snap` : 'Unsnapped'}
                  </span>
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Interactive Directed OSM Shortest-Path Tester */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm space-y-4">
        <div className="flex items-center gap-2">
          <Compass className="h-4 w-4 text-teal-600" />
          <h3 className="text-sm font-bold text-slate-900">
            Directed OSM Shortest-Path Explorer
          </h3>
        </div>
        <form onSubmit={handleShortestPathLookup} className="grid grid-cols-1 gap-3 md:grid-cols-5">
          <div>
            <label className="block text-[11px] font-semibold text-slate-600">Origin Facility</label>
            <select
              value={sourceCode}
              onChange={(e) => setSourceCode(e.target.value)}
              className="mt-1 block w-full rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs"
            >
              {facilities.map((f) => (
                <option key={`src-${f.code}`} value={f.code}>
                  {f.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-[11px] font-semibold text-slate-600">
              Destination Facility
            </label>
            <select
              value={targetCode}
              onChange={(e) => setTargetCode(e.target.value)}
              className="mt-1 block w-full rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs"
            >
              {facilities.map((f) => (
                <option key={`tgt-${f.code}`} value={f.code}>
                  {f.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-[11px] font-semibold text-slate-600">Weight Metric</label>
            <select
              value={weightMetric}
              onChange={(e) => setWeightMetric(e.target.value)}
              className="mt-1 block w-full rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs"
            >
              <option value="distance_km">Shortest Road Distance (km)</option>
              <option value="estimated_travel_time_min">Shortest Est. Travel Time (min)</option>
            </select>
          </div>
          <div>
            <label className="block text-[11px] font-semibold text-slate-600">
              Closed OSM Way IDs (Optional)
            </label>
            <input
              type="text"
              value={closedWaysText}
              onChange={(e) => setClosedWaysText(e.target.value)}
              placeholder="e.g., 210788741"
              className="mt-1 block w-full rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs"
            />
          </div>
          <div className="flex items-end">
            <button
              type="submit"
              disabled={queryingPath}
              className="inline-flex w-full items-center justify-center gap-1.5 rounded-lg bg-teal-600 px-4 py-2 text-xs font-semibold text-white hover:bg-teal-700 disabled:opacity-50"
            >
              <RouteIcon className="h-3.5 w-3.5" />
              {queryingPath ? 'Computing...' : 'Compute Path'}
            </button>
          </div>
        </form>

        {pathError && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-800">
            {pathError}
          </div>
        )}

        {pathResult && (
          <div className="rounded-lg border border-slate-200 bg-slate-50/70 p-4 text-xs space-y-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-bold text-slate-900">
                  {pathResult.source_code} &rarr; {pathResult.target_code}
                </span>
                <StatusBadge
                  status={pathResult.reachable ? 'active' : 'critical'}
                  label={pathResult.reachable ? 'Reachable' : 'Unreachable'}
                />
                <span
                  className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                    pathResult.source_type === 'osm_road_network'
                      ? 'bg-teal-100 text-teal-800'
                      : 'bg-amber-100 text-amber-800'
                  }`}
                >
                  {pathResult.source_type === 'osm_road_network'
                    ? 'OSM Directed Graph'
                    : 'Synthetic Fallback'}
                </span>
              </div>
              {pathResult.reachable && (
                <span className="font-semibold text-slate-800">
                  {pathResult.distance_km} km &bull; {pathResult.estimated_travel_time_min} min
                  (est.) &bull; {(pathResult.geometry || []).length} geometry pts
                </span>
              )}
            </div>
            {pathResult.road_names?.length > 0 && (
              <p className="text-slate-600">
                <strong>Major Roads:</strong>{' '}
                {pathResult.road_names
                  .filter((n) => n && !n.startsWith('Unnamed'))
                  .slice(0, 8)
                  .join(' → ') || pathResult.road_names.slice(0, 6).join(' → ')}
              </p>
            )}
            <p className="text-[11px] text-slate-500">
              {pathResult.note} &bull; {pathResult.attribution}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
