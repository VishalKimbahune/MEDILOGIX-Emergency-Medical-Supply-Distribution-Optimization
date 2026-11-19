import React, { useMemo, useState } from 'react';
import L from 'leaflet';
import {
  CircleMarker,
  MapContainer,
  Marker,
  Polyline,
  Popup,
  TileLayer,
} from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

const PUNE_CENTER = [18.545, 73.86];

const PRIORITY_COLORS = {
  critical: '#dc2626',
  high: '#f97316',
  normal: '#059669',
};

const ROUTE_PALETTE = [
  '#0d9488', // teal
  '#2563eb', // blue
  '#7c3aed', // violet
  '#d97706', // amber
  '#0891b2', // cyan
  '#4f46e5', // indigo
  '#059669', // emerald
  '#db2777', // pink
];

function createWarehouseIcon(code, isDisabled = false) {
  return L.divIcon({
    className: 'medilogix-warehouse-marker',
    html: `<div style="
      display:flex;align-items:center;justify-content:center;
      width:28px;height:28px;border-radius:6px;
      background:${isDisabled ? '#64748b' : '#0b162c'};
      color:#ffffff;font-weight:700;font-size:10px;
      border:2px solid ${isDisabled ? '#ef4444' : '#14b8a6'};
      box-shadow:0 2px 6px rgba(0,0,0,0.35);
      ${isDisabled ? 'text-decoration:line-through;opacity:0.85;' : ''}
    ">${code.replace('WH-', 'W')}</div>`,
    iconSize: [28, 28],
    iconAnchor: [14, 14],
  });
}

function createStopBadgeIcon(seq, color) {
  return L.divIcon({
    className: 'medilogix-stop-badge',
    html: `<div style="
      display:flex;align-items:center;justify-content:center;
      width:20px;height:20px;border-radius:9999px;
      background:${color};color:#ffffff;font-weight:700;font-size:10px;
      border:2px solid #ffffff;box-shadow:0 1px 4px rgba(0,0,0,0.4);
    ">${seq}</div>`,
    iconSize: [20, 20],
    iconAnchor: [10, 10],
  });
}

function formatSourceLabel(source) {
  if (source === 'osm' || source === 'osm_road_network') {
    return 'OpenStreetMap Road Network';
  }
  if (source === 'synthetic_fallback') {
    return 'Synthetic Corridor Fallback';
  }
  return null;
}

function formatObjectiveLabel(objective) {
  if (objective === 'min_time') return 'Min Estimated Time';
  if (objective === 'min_distance') return 'Min Road Distance';
  return null;
}

export default function PuneNetworkMap({
  warehouses = [],
  hospitals = [],
  vehicleRoutes = [],
  closedCorridors = [],
  closedOsmWays = [],
  disabledWarehouses = [],
  unreachableHospitals = [],
  routingSource = null,
  routingObjective = null,
  fallbackWarning = null,
  title = 'Pune & Pimpri-Chinchwad Medical Logistics Network',
  subtitle = 'OpenStreetMap road geometry — Fictional simulation hubs, synthetic hospital profiles & speed-profile travel time estimates (not live traffic or GPS)',
  heightClass = 'h-[360px]',
}) {
  const [showWarehouses, setShowWarehouses] = useState(true);
  const [showHospitals, setShowHospitals] = useState(true);
  const [showRoutes, setShowRoutes] = useState(true);
  const [showClosedRoads, setShowClosedRoads] = useState(true);
  const [vehicleFilter, setVehicleFilter] = useState('all');
  const [priorityFilter, setPriorityFilter] = useState('all');

  const disabledSet = useMemo(() => new Set(disabledWarehouses || []), [disabledWarehouses]);
  const unreachableSet = useMemo(() => new Set(unreachableHospitals || []), [unreachableHospitals]);

  const uniqueVehicleCodes = useMemo(
    () => Array.from(new Set((vehicleRoutes || []).map((r) => r.vehicle_code).filter(Boolean))),
    [vehicleRoutes]
  );

  const visibleRoutes = useMemo(() => {
    if (!showRoutes) return [];
    if (vehicleFilter === 'all') return vehicleRoutes || [];
    return (vehicleRoutes || []).filter((r) => r.vehicle_code === vehicleFilter);
  }, [showRoutes, vehicleFilter, vehicleRoutes]);

  const visibleHospitals = useMemo(() => {
    if (!showHospitals) return [];
    if (priorityFilter === 'all') return hospitals || [];
    return (hospitals || []).filter((h) => h.priority_level === priorityFilter);
  }, [showHospitals, priorityFilter, hospitals]);

  const effectiveSource = useMemo(() => {
    if (routingSource) return routingSource;
    const firstRoute = (vehicleRoutes || [])[0];
    return firstRoute?.routing_source || null;
  }, [routingSource, vehicleRoutes]);

  const effectiveObjective = useMemo(() => {
    if (routingObjective) return routingObjective;
    const firstRoute = (vehicleRoutes || [])[0];
    return firstRoute?.routing_objective || null;
  }, [routingObjective, vehicleRoutes]);

  const isOsmActive = effectiveSource === 'osm' || effectiveSource === 'osm_road_network';
  const sourceLabel = formatSourceLabel(effectiveSource);
  const objectiveLabel = formatObjectiveLabel(effectiveObjective);
  const hasClosedRoads = closedCorridors.length > 0 || closedOsmWays.length > 0;

  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 px-4 py-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
            {sourceLabel && (
              <span
                className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${
                  isOsmActive
                    ? 'bg-teal-50 text-teal-800 ring-1 ring-teal-200'
                    : 'bg-amber-50 text-amber-800 ring-1 ring-amber-200'
                }`}
              >
                {sourceLabel}
              </span>
            )}
            {objectiveLabel && (
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-700">
                {objectiveLabel}
              </span>
            )}
          </div>
          <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p>
        </div>

        <div className="flex flex-wrap items-center gap-3 text-xs text-slate-600">
          <span className="inline-flex items-center gap-1">
            <span className="h-3 w-3 rounded bg-navy-900 ring-1 ring-teal-500" /> Warehouse
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="h-2.5 w-2.5 rounded-full bg-red-600" /> Critical
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="h-2.5 w-2.5 rounded-full bg-orange-500" /> High
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="h-2.5 w-2.5 rounded-full bg-emerald-600" /> Normal
          </span>
          {vehicleRoutes.length > 0 && (
            <span className="inline-flex items-center gap-1">
              <span
                className={`h-0.5 w-4 ${
                  isOsmActive ? 'bg-teal-600' : 'border-b-2 border-dashed border-teal-600'
                }`}
              />
              {isOsmActive ? 'OSM Road Route' : 'Synthetic Fallback Route'}
            </span>
          )}
          {hasClosedRoads && (
            <span className="inline-flex items-center gap-1 font-medium text-red-700">
              <span className="h-0.5 w-4 border-b-2 border-dashed border-red-600" /> Closed Road
            </span>
          )}
          {unreachableSet.size > 0 && (
            <span className="inline-flex items-center gap-1 font-medium text-red-700">
              <span className="h-2.5 w-2.5 rounded-full border-2 border-red-600 bg-white" /> Unreachable
            </span>
          )}
        </div>
      </div>

      {(fallbackWarning || unreachableSet.size > 0) && (
        <div className="flex flex-wrap items-center gap-3 border-b border-amber-200 bg-amber-50 px-4 py-2 text-xs text-amber-900">
          {fallbackWarning && (
            <span>
              <strong>Fallback Notice:</strong> {fallbackWarning}
            </span>
          )}
          {unreachableSet.size > 0 && (
            <span className="text-red-800">
              <strong>Unreachable Hospital(s):</strong> {Array.from(unreachableSet).join(', ')} (not
              routed under current road closures/restrictions)
            </span>
          )}
        </div>
      )}

      {/* Interactive Map Layer & Filter Controls */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 bg-slate-50/70 px-4 py-2 text-[11px] text-slate-700">
        <div className="flex flex-wrap items-center gap-3">
          <label className="inline-flex cursor-pointer items-center gap-1.5 font-medium">
            <input
              type="checkbox"
              checked={showWarehouses}
              onChange={(e) => setShowWarehouses(e.target.checked)}
              className="rounded border-slate-300 text-teal-600 focus:ring-teal-600"
            />
            Warehouses
          </label>
          <label className="inline-flex cursor-pointer items-center gap-1.5 font-medium">
            <input
              type="checkbox"
              checked={showHospitals}
              onChange={(e) => setShowHospitals(e.target.checked)}
              className="rounded border-slate-300 text-teal-600 focus:ring-teal-600"
            />
            Hospitals
          </label>
          {vehicleRoutes.length > 0 && (
            <label className="inline-flex cursor-pointer items-center gap-1.5 font-medium">
              <input
                type="checkbox"
                checked={showRoutes}
                onChange={(e) => setShowRoutes(e.target.checked)}
                className="rounded border-slate-300 text-teal-600 focus:ring-teal-600"
              />
              Routes ({visibleRoutes.length}/{vehicleRoutes.length})
            </label>
          )}
          {hasClosedRoads && (
            <label className="inline-flex cursor-pointer items-center gap-1.5 font-medium text-red-700">
              <input
                type="checkbox"
                checked={showClosedRoads}
                onChange={(e) => setShowClosedRoads(e.target.checked)}
                className="rounded border-slate-300 text-red-600 focus:ring-red-600"
              />
              Closed Roads
            </label>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {uniqueVehicleCodes.length > 0 && (
            <select
              aria-label="Filter routes by vehicle"
              value={vehicleFilter}
              onChange={(e) => setVehicleFilter(e.target.value)}
              className="rounded-md border border-slate-300 bg-white px-2 py-1 text-[11px] font-medium text-slate-700 focus:border-teal-600 focus:outline-none"
            >
              <option value="all">All Vehicles ({uniqueVehicleCodes.length})</option>
              {uniqueVehicleCodes.map((code) => (
                <option key={code} value={code}>
                  Vehicle: {code}
                </option>
              ))}
            </select>
          )}
          <select
            aria-label="Filter hospitals by priority"
            value={priorityFilter}
            onChange={(e) => setPriorityFilter(e.target.value)}
            className="rounded-md border border-slate-300 bg-white px-2 py-1 text-[11px] font-medium text-slate-700 focus:border-teal-600 focus:outline-none"
          >
            <option value="all">All Priorities</option>
            <option value="critical">Priority: Critical</option>
            <option value="high">Priority: High</option>
            <option value="normal">Priority: Normal</option>
          </select>
        </div>
      </div>

      <div className={`${heightClass} w-full`}>
        <MapContainer
          center={PUNE_CENTER}
          zoom={11}
          scrollWheelZoom={false}
          preferCanvas={true}
          className="h-full w-full"
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors (ODbL 1.0)'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          {/* Closed Synthetic Corridors (Dashed Red) */}
          {showClosedRoads &&
            closedCorridors.map((cor) => (
            <Polyline
              key={`closed-cor-${cor.route_code}`}
              positions={[
                [cor.from_lat, cor.from_lon],
                [cor.to_lat, cor.to_lon],
              ]}
              pathOptions={{
                color: '#dc2626',
                weight: 3.5,
                dashArray: '8 6',
                opacity: 0.85,
              }}
            >
              <Popup>
                <div className="text-xs">
                  <p className="font-bold text-red-700">CLOSED CORRIDOR — {cor.route_code}</p>
                  <p className="text-slate-600">
                    {cor.warehouse_code} &harr; {cor.hospital_code}
                  </p>
                  <p className="text-slate-500">Est. Distance: {cor.distance_km} km</p>
                </div>
              </Popup>
            </Polyline>
          ))}

          {/* Closed OSM Street Ways (Bold Dashed Crimson Street Polylines) */}
          {showClosedRoads &&
            closedOsmWays.map((way) =>
            (way.segments || []).map((seg, segIdx) => (
              <Polyline
                key={`closed-osm-${way.way_id}-${segIdx}`}
                positions={seg}
                pathOptions={{
                  color: '#b91c1c',
                  weight: 5,
                  dashArray: '6 6',
                  opacity: 0.95,
                }}
              >
                <Popup>
                  <div className="space-y-0.5 text-xs">
                    <p className="font-bold text-red-700">CLOSED OSM ROAD</p>
                    <p className="font-semibold text-slate-900">{way.name}</p>
                    <p className="text-slate-600">
                      OSM Way ID: <strong>{way.way_id}</strong> &bull; Class: {way.highway}
                    </p>
                    <p className="text-[11px] text-slate-500">
                      Excluded from directed shortest-path and OR-Tools vehicle routing.
                    </p>
                  </div>
                </Popup>
              </Polyline>
            ))
          )}

          {/* Solved OR-Tools Vehicle Routes */}
          {visibleRoutes.map((route, idx) => {
            const color = ROUTE_PALETTE[idx % ROUTE_PALETTE.length];
            const routeIsOsm =
              route.routing_source === 'osm' ||
              (Array.isArray(route.route_geometry) &&
                route.route_geometry.length > (route.route_coordinates?.length || 0));

            const polylineCoords =
              Array.isArray(route.route_geometry) && route.route_geometry.length >= 2
                ? route.route_geometry
                : (route.route_coordinates || [])
                    .filter((pt) => pt.lat !== undefined && pt.lon !== undefined)
                    .map((pt) => [pt.lat, pt.lon]);

            if (polylineCoords.length < 2) return null;

            const stopList = route.delivery_stops || route.stops || [];
            const roadSample = (route.road_names || [])
              .filter((n) => n && !n.startsWith('Unnamed'))
              .slice(0, 5);

            return (
              <React.Fragment
                key={`route-${route.id || idx}-${route.vehicle_code}-${route.trip_number}`}
              >
                <Polyline
                  positions={polylineCoords}
                  pathOptions={{
                    color,
                    weight: routeIsOsm ? 4 : 3.5,
                    opacity: 0.88,
                    dashArray: routeIsOsm ? undefined : '7 5',
                  }}
                >
                  <Popup>
                    <div className="space-y-1 text-xs">
                      <p className="font-bold text-slate-900">
                        {route.vehicle_code} (Wave #{route.trip_number || 1})
                      </p>
                      <p className="text-slate-600">
                        Depot: <strong>{route.warehouse_code}</strong> &bull; Source:{' '}
                        <strong>{routeIsOsm ? 'OSM Road Network' : 'Synthetic Fallback'}</strong>
                      </p>
                      <p className="text-slate-600">
                        Load: {route.total_load_kg} / {route.capacity_kg} kg ({route.utilization_pct}
                        %)
                      </p>
                      <p className="text-slate-600">
                        {routeIsOsm ? 'Road Distance' : 'Est. Distance'}:{' '}
                        <strong>{route.route_distance_km} km</strong> &bull; Est. Time:{' '}
                        <strong>{route.estimated_duration_min} min</strong>
                      </p>
                      <p className="text-slate-500">
                        Stops:{' '}
                        {stopList.map((s) => `${s.stop_sequence}. ${s.hospital_code}`).join(' → ')}
                      </p>
                      {roadSample.length > 0 && (
                        <p className="text-[11px] text-slate-500">
                          Via: {roadSample.join(' · ')}
                        </p>
                      )}
                      <p className="text-[10px] italic text-slate-400">
                        Travel time uses assumed road-class speed profiles (not live traffic).
                      </p>
                    </div>
                  </Popup>
                </Polyline>

                {/* Numbered Stop Markers along Route */}
                {(route.route_coordinates || [])
                  .filter((pt) => pt.node_type === 'hospital')
                  .map((pt) => (
                    <Marker
                      key={`stop-badge-${idx}-${pt.code}-${pt.sequence}`}
                      position={[pt.lat + 0.0011 * (idx % 3), pt.lon + 0.0011 * (idx % 3)]}
                      icon={createStopBadgeIcon(pt.sequence, color)}
                    >
                      <Popup>
                        <div className="text-xs">
                          <p className="font-bold text-slate-900">
                            Stop #{pt.sequence}: {pt.code}
                          </p>
                          <p className="text-slate-600">{pt.name}</p>
                          <p className="text-slate-500">
                            Assigned: {route.vehicle_code} (Wave #{route.trip_number || 1})
                          </p>
                        </div>
                      </Popup>
                    </Marker>
                  ))}
              </React.Fragment>
            );
          })}

          {/* Warehouse Markers (Distinct Dark-Navy Square Depot Badges) */}
          {showWarehouses &&
            warehouses.map((wh) => {
            const isDisabled = disabledSet.has(wh.code);
            return (
              <Marker
                key={`wh-${wh.code}`}
                position={[wh.latitude, wh.longitude]}
                icon={createWarehouseIcon(wh.code, isDisabled)}
              >
                <Popup>
                  <div className="text-xs">
                    <p className="font-bold text-slate-900">
                      {wh.code} — {wh.name}
                    </p>
                    {isDisabled && (
                      <p className="font-semibold text-red-600">SIMULATED OUTAGE (DISABLED)</p>
                    )}
                    <p className="text-slate-600">
                      Area: {wh.area}, {wh.city}
                    </p>
                    <p className="text-slate-600">
                      Capacity: {wh.storage_capacity_units} units
                    </p>
                  </div>
                </Popup>
              </Marker>
            );
          })}

          {/* Hospital Markers (Priority-Colored Circles + Unreachable Halo) */}
          {visibleHospitals.map((hosp) => {
            const color = PRIORITY_COLORS[hosp.priority_level] || '#059669';
            const isUnreachable = unreachableSet.has(hosp.code);
            return (
              <React.Fragment key={`hosp-${hosp.code}`}>
                {isUnreachable && (
                  <CircleMarker
                    center={[hosp.latitude, hosp.longitude]}
                    radius={12}
                    pathOptions={{
                      color: '#dc2626',
                      fillColor: '#fecaca',
                      fillOpacity: 0.35,
                      weight: 2.5,
                      dashArray: '4 3',
                    }}
                  />
                )}
                <CircleMarker
                  center={[hosp.latitude, hosp.longitude]}
                  radius={7}
                  pathOptions={{
                    color: isUnreachable ? '#991b1b' : color,
                    fillColor: color,
                    fillOpacity: 0.85,
                    weight: 2,
                  }}
                >
                  <Popup>
                    <div className="text-xs">
                      <p className="font-bold text-slate-900">
                        {hosp.code} — {hosp.name}
                      </p>
                      {isUnreachable && (
                        <p className="font-bold text-red-700">
                          UNREACHABLE — No open road path from assigned depot
                        </p>
                      )}
                      <p className="text-slate-600">
                        Area: {hosp.area}, {hosp.city}
                      </p>
                      <p className="capitalize text-slate-600">
                        Priority: <span className="font-semibold">{hosp.priority_level}</span>
                      </p>
                    </div>
                  </Popup>
                </CircleMarker>
              </React.Fragment>
            );
          })}
        </MapContainer>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 bg-slate-50 px-4 py-1.5 text-[11px] text-slate-500">
        <span>
          <strong>OSM road geometry | Estimated travel time | Not live traffic or GPS.</strong>
        </span>
        <span>
          Attribution: <strong>&copy; OpenStreetMap contributors (ODbL 1.0)</strong>
        </span>
      </div>
    </div>
  );
}
