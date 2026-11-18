import React from 'react';
import { CircleMarker, MapContainer, Popup, TileLayer } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

const PUNE_CENTER = [18.545, 73.86];

const PRIORITY_COLORS = {
  critical: '#dc2626',
  high: '#f97316',
  normal: '#059669',
};

export default function PuneNetworkMap({ warehouses = [], hospitals = [] }) {
  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 px-4 py-3">
        <div>
          <h2 className="text-sm font-semibold text-slate-900">
            Pune &amp; Pimpri-Chinchwad Medical Logistics Network
          </h2>
          <p className="text-xs text-slate-500">
            OpenStreetMap base layer — Fictional simulation hubs &amp; synthetic hospital profiles
          </p>
        </div>
        <div className="flex items-center gap-3 text-xs text-slate-600">
          <span className="inline-flex items-center gap-1">
            <span className="h-2.5 w-2.5 rounded-full bg-teal-600" /> Warehouse
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
        </div>
      </div>

      <div className="h-[360px] w-full">
        <MapContainer
          center={PUNE_CENTER}
          zoom={11}
          scrollWheelZoom={false}
          className="h-full w-full"
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          {warehouses.map((wh) => (
            <CircleMarker
              key={`wh-${wh.code}`}
              center={[wh.latitude, wh.longitude]}
              radius={9}
              pathOptions={{
                color: '#0f766e',
                fillColor: '#14b8a6',
                fillOpacity: 0.9,
                weight: 2,
              }}
            >
              <Popup>
                <div className="text-xs">
                  <p className="font-bold text-slate-900">{wh.code} — {wh.name}</p>
                  <p className="text-slate-600">Area: {wh.area}, {wh.city}</p>
                  <p className="text-slate-600">Capacity: {wh.storage_capacity_units} units</p>
                </div>
              </Popup>
            </CircleMarker>
          ))}

          {hospitals.map((hosp) => {
            const color = PRIORITY_COLORS[hosp.priority_level] || '#059669';
            return (
              <CircleMarker
                key={`hosp-${hosp.code}`}
                center={[hosp.latitude, hosp.longitude]}
                radius={7}
                pathOptions={{
                  color,
                  fillColor: color,
                  fillOpacity: 0.85,
                  weight: 2,
                }}
              >
                <Popup>
                  <div className="text-xs">
                    <p className="font-bold text-slate-900">{hosp.code} — {hosp.name}</p>
                    <p className="text-slate-600">Area: {hosp.area}, {hosp.city}</p>
                    <p className="capitalize text-slate-600">
                      Priority: <span className="font-semibold">{hosp.priority_level}</span>
                    </p>
                  </div>
                </Popup>
              </CircleMarker>
            );
          })}
        </MapContainer>
      </div>
    </div>
  );
}
