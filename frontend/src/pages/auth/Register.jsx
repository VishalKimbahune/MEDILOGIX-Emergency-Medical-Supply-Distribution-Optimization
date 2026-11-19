import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { AlertCircle, Building2, CheckCircle2, MapPin, Truck, Warehouse } from 'lucide-react';
import AuthLayout from './AuthLayout';
import { fetchPublicOrganizations, registerUser } from '../../services/authService';

const ROLE_OPTIONS = [
  { value: 'hospital', label: 'Hospital', desc: 'Onboard hospital & order', icon: Building2 },
  { value: 'warehouse', label: 'Warehouse', desc: 'Onboard depot & stock', icon: Warehouse },
  { value: 'delivery', label: 'Delivery', desc: 'Onboard driver & vehicle', icon: Truck },
];

// Accurate Pune & Pimpri-Chinchwad locality presets so users can pick a location effortlessly
const PUNE_AREA_PRESETS = [
  { area: 'Shivajinagar', lat: 18.5308, lon: 73.8475 },
  { area: 'Erandwane', lat: 18.5089, lon: 73.8295 },
  { area: 'Kothrud', lat: 18.5074, lon: 73.8077 },
  { area: 'Aundh', lat: 18.558, lon: 73.8075 },
  { area: 'Baner', lat: 18.559, lon: 73.7868 },
  { area: 'Wakad', lat: 18.5987, lon: 73.7617 },
  { area: 'Hinjewadi', lat: 18.5913, lon: 73.7389 },
  { area: 'Viman Nagar', lat: 18.5679, lon: 73.9143 },
  { area: 'Koregaon Park', lat: 18.5362, lon: 73.8939 },
  { area: 'Hadapsar', lat: 18.5089, lon: 73.926 },
  { area: 'Kondhwa', lat: 18.4695, lon: 73.889 },
  { area: 'Swargate', lat: 18.5018, lon: 73.8636 },
  { area: 'Katraj', lat: 18.4529, lon: 73.8652 },
  { area: 'Pimpri-Chinchwad', lat: 18.6298, lon: 73.7997 },
];

export default function Register() {
  const navigate = useNavigate();
  const [orgs, setOrgs] = useState({ hospitals: [], warehouses: [] });
  const [loadingOrgs, setLoadingOrgs] = useState(true);

  const [role, setRole] = useState('hospital');
  const [hospitalMode, setHospitalMode] = useState('new'); // 'new' | 'existing'
  const [warehouseMode, setWarehouseMode] = useState('new'); // 'new' | 'existing'

  const [account, setAccount] = useState({
    full_name: '',
    email: '',
    phone_number: '',
    password: '',
    confirm_password: '',
    associated_hospital_id: '',
    associated_warehouse_id: '',
  });

  const [newHospital, setNewHospital] = useState({
    name: '',
    area: 'Erandwane',
    city: 'Pune',
    latitude: '18.5089',
    longitude: '73.8295',
    bed_capacity: '180',
    priority_level: 'high',
  });

  const [newWarehouse, setNewWarehouse] = useState({
    name: '',
    area: 'Viman Nagar',
    city: 'Pune',
    latitude: '18.5679',
    longitude: '73.9143',
    storage_capacity_units: '2500',
  });

  const [newVehicle, setNewVehicle] = useState({
    warehouse_id: '',
    vehicle_type: 'medical_van',
    capacity_kg: '1200',
    vehicle_code: '',
  });

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchPublicOrganizations()
      .then((data) => {
        const hospitals = data?.hospitals || [];
        const warehouses = data?.warehouses || [];
        setOrgs({ hospitals, warehouses });
        if (warehouses.length > 0) {
          setNewVehicle((prev) => ({
            ...prev,
            warehouse_id: prev.warehouse_id || String(warehouses[0].id),
          }));
        }
      })
      .catch(() => {
        setError('Unable to load active Pune depots. Ensure the backend API is running.');
      })
      .finally(() => setLoadingOrgs(false));
  }, []);

  function applyPreset(presetName, target) {
    const match = PUNE_AREA_PRESETS.find((p) => p.area === presetName);
    if (!match) return;
    if (target === 'hospital') {
      setNewHospital((prev) => ({
        ...prev,
        area: match.area,
        latitude: String(match.lat),
        longitude: String(match.lon),
      }));
    } else {
      setNewWarehouse((prev) => ({
        ...prev,
        area: match.area,
        latitude: String(match.lat),
        longitude: String(match.lon),
      }));
    }
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');

    if (account.password !== account.confirm_password) {
      setError('Password and confirm password do not match.');
      return;
    }

    const payload = {
      full_name: account.full_name.trim(),
      email: account.email.trim(),
      phone_number: account.phone_number.trim() || null,
      role,
      password: account.password,
      confirm_password: account.confirm_password,
    };

    if (role === 'hospital') {
      if (hospitalMode === 'new') {
        payload.new_hospital = {
          name: newHospital.name.trim(),
          area: newHospital.area.trim(),
          city: newHospital.city.trim() || 'Pune',
          latitude: Number(newHospital.latitude),
          longitude: Number(newHospital.longitude),
          bed_capacity: parseInt(newHospital.bed_capacity, 10),
          priority_level: newHospital.priority_level,
        };
      } else {
        if (!account.associated_hospital_id) {
          setError('Please select an existing hospital.');
          return;
        }
        payload.associated_hospital_id = Number(account.associated_hospital_id);
      }
    } else if (role === 'warehouse') {
      if (warehouseMode === 'new') {
        payload.new_warehouse = {
          name: newWarehouse.name.trim(),
          area: newWarehouse.area.trim(),
          city: newWarehouse.city.trim() || 'Pune',
          latitude: Number(newWarehouse.latitude),
          longitude: Number(newWarehouse.longitude),
          storage_capacity_units: parseInt(newWarehouse.storage_capacity_units, 10),
        };
      } else {
        if (!account.associated_warehouse_id) {
          setError('Please select an existing warehouse.');
          return;
        }
        payload.associated_warehouse_id = Number(account.associated_warehouse_id);
      }
    } else if (role === 'delivery') {
      if (!newVehicle.warehouse_id) {
        setError('Please select your base warehouse depot.');
        return;
      }
      payload.new_vehicle = {
        warehouse_id: Number(newVehicle.warehouse_id),
        vehicle_type: newVehicle.vehicle_type,
        capacity_kg: Number(newVehicle.capacity_kg),
        vehicle_code: newVehicle.vehicle_code.trim() || null,
      };
    }

    setSubmitting(true);
    try {
      const res = await registerUser(payload);
      navigate('/pending-approval', {
        replace: true,
        state: {
          email: payload.email,
          role: payload.role,
          message: res?.message,
          devVerifyUrl: res?.dev_verify_url || null,
        },
      });
    } catch (err) {
      const detail = err?.response?.data?.detail;
      if (typeof detail === 'string') {
        setError(detail);
      } else if (Array.isArray(detail) && detail[0]?.msg) {
        setError(detail[0].msg);
      } else {
        setError('Registration failed. Please check all required fields and try again.');
      }
    } finally {
      setSubmitting(false);
    }
  }

  const pwChecks = [
    { ok: account.password.length >= 8, label: '8+ chars' },
    { ok: /[A-Z]/.test(account.password), label: 'Uppercase' },
    { ok: /[a-z]/.test(account.password), label: 'Lowercase' },
    { ok: /\d/.test(account.password), label: 'Number' },
  ];

  return (
    <AuthLayout
      title="Register on MEDILOGIX"
      subtitle="Onboard a new Hospital, Warehouse, or Delivery Driver. Admin approval activates your facility across the network."
    >
      {error && (
        <div className="mb-4 flex items-start gap-2.5 rounded-xl border border-red-200 bg-red-50 p-3.5 text-xs text-red-800">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-600" />
          <span>{error}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Role Selector */}
        <div>
          <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-600">
            Select Portal Role
          </label>
          <div className="grid grid-cols-3 gap-2">
            {ROLE_OPTIONS.map(({ value, label, icon: Icon }) => {
              const active = role === value;
              return (
                <button
                  key={value}
                  type="button"
                  onClick={() => setRole(value)}
                  className={`flex flex-col items-center rounded-xl border p-2.5 text-center transition ${
                    active
                      ? 'border-teal-600 bg-teal-50 text-teal-900 ring-1 ring-teal-600'
                      : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300'
                  }`}
                >
                  <Icon className={`h-4 w-4 ${active ? 'text-teal-700' : 'text-slate-400'}`} />
                  <span className="mt-1 text-xs font-semibold">{label}</span>
                </button>
              );
            })}
          </div>
          <p className="mt-1 text-[11px] text-slate-500">
            Admin accounts are provisioned internally and cannot be publicly registered.
          </p>
        </div>

        {/* Account Contact Details */}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-xs font-semibold text-slate-700">
              {role === 'delivery' ? 'Driver Full Name' : 'Coordinator / Manager Name'}
            </label>
            <input
              type="text"
              required
              value={account.full_name}
              onChange={(e) => setAccount({ ...account, full_name: e.target.value })}
              placeholder={role === 'delivery' ? 'Rohan Deshmukh' : 'Dr. Aarti Joshi'}
              className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:border-sky-600 focus:outline-none"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold text-slate-700">
              Phone Number {role === 'delivery' ? '(Required)' : '(Optional)'}
            </label>
            <input
              type="text"
              required={role === 'delivery'}
              value={account.phone_number}
              onChange={(e) => setAccount({ ...account, phone_number: e.target.value })}
              placeholder="+91-98XXXXXXXX"
              className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:border-sky-600 focus:outline-none"
            />
          </div>
        </div>

        <div>
          <label className="mb-1 block text-xs font-semibold text-slate-700">Work Email</label>
          <input
            type="email"
            required
            value={account.email}
            onChange={(e) => setAccount({ ...account, email: e.target.value })}
            placeholder="name@punehealth.org"
            className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:border-sky-600 focus:outline-none"
          />
        </div>

        {/* ============================================================
            ROLE-SPECIFIC ONBOARDING DETAILS
           ============================================================ */}

        {/* HOSPITAL ONBOARDING */}
        {role === 'hospital' && (
          <div className="space-y-3 rounded-xl border border-teal-200/80 bg-teal-50/40 p-3.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-teal-900">
                Hospital Details
              </span>
              <div className="inline-flex rounded-lg border border-teal-200 bg-white p-0.5 text-[11px] font-semibold">
                <button
                  type="button"
                  onClick={() => setHospitalMode('new')}
                  className={`rounded-md px-2.5 py-1 ${
                    hospitalMode === 'new' ? 'bg-teal-600 text-white' : 'text-slate-600'
                  }`}
                >
                  New Hospital
                </button>
                <button
                  type="button"
                  onClick={() => setHospitalMode('existing')}
                  className={`rounded-md px-2.5 py-1 ${
                    hospitalMode === 'existing' ? 'bg-teal-600 text-white' : 'text-slate-600'
                  }`}
                >
                  Join Existing
                </button>
              </div>
            </div>

            {hospitalMode === 'new' ? (
              <div className="space-y-3">
                <div>
                  <label className="mb-1 block text-[11px] font-semibold text-slate-700">
                    Hospital Name
                  </label>
                  <input
                    required
                    value={newHospital.name}
                    onChange={(e) => setNewHospital({ ...newHospital, name: e.target.value })}
                    placeholder="e.g., Deenanath Emergency Medical Center"
                    className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                  />
                </div>

                <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
                  <div>
                    <label className="mb-1 block text-[11px] font-semibold text-slate-700">
                      Pune Area Quick-Pick
                    </label>
                    <select
                      value={
                        PUNE_AREA_PRESETS.some((p) => p.area === newHospital.area)
                          ? newHospital.area
                          : ''
                      }
                      onChange={(e) => applyPreset(e.target.value, 'hospital')}
                      className="w-full rounded-lg border border-slate-300 bg-white px-2.5 py-2 text-xs"
                    >
                      <option value="">-- Pick locality (auto-fills GPS) --</option>
                      {PUNE_AREA_PRESETS.map((p) => (
                        <option key={p.area} value={p.area}>
                          {p.area}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="mb-1 block text-[11px] font-semibold text-slate-700">
                      Area / Locality Name
                    </label>
                    <input
                      required
                      value={newHospital.area}
                      onChange={(e) => setNewHospital({ ...newHospital, area: e.target.value })}
                      placeholder="e.g., Erandwane"
                      className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2.5">
                  <div>
                    <label className="mb-1 flex items-center gap-1 text-[11px] font-semibold text-slate-700">
                      <MapPin className="h-3 w-3 text-teal-600" />
                      Latitude (Pune)
                    </label>
                    <input
                      type="number"
                      step="0.0001"
                      min="18.2"
                      max="18.9"
                      required
                      value={newHospital.latitude}
                      onChange={(e) => setNewHospital({ ...newHospital, latitude: e.target.value })}
                      className="w-full rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs"
                    />
                  </div>
                  <div>
                    <label className="mb-1 flex items-center gap-1 text-[11px] font-semibold text-slate-700">
                      <MapPin className="h-3 w-3 text-teal-600" />
                      Longitude (Pune)
                    </label>
                    <input
                      type="number"
                      step="0.0001"
                      min="73.5"
                      max="74.2"
                      required
                      value={newHospital.longitude}
                      onChange={(e) => setNewHospital({ ...newHospital, longitude: e.target.value })}
                      className="w-full rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2.5">
                  <div>
                    <label className="mb-1 block text-[11px] font-semibold text-slate-700">
                      Bed Capacity
                    </label>
                    <input
                      type="number"
                      min="1"
                      max="10000"
                      required
                      value={newHospital.bed_capacity}
                      onChange={(e) =>
                        setNewHospital({ ...newHospital, bed_capacity: e.target.value })
                      }
                      className="w-full rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-[11px] font-semibold text-slate-700">
                      Emergency Priority Tier
                    </label>
                    <select
                      value={newHospital.priority_level}
                      onChange={(e) =>
                        setNewHospital({ ...newHospital, priority_level: e.target.value })
                      }
                      className="w-full rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs"
                    >
                      <option value="critical">Critical (Tier 1)</option>
                      <option value="high">High (Tier 2)</option>
                      <option value="normal">Normal (Tier 3)</option>
                    </select>
                  </div>
                </div>
              </div>
            ) : (
              <div>
                <label className="mb-1 block text-[11px] font-semibold text-slate-700">
                  Select Existing Hospital
                </label>
                <select
                  required
                  disabled={loadingOrgs}
                  value={account.associated_hospital_id}
                  onChange={(e) =>
                    setAccount({ ...account, associated_hospital_id: e.target.value })
                  }
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs"
                >
                  <option value="">-- Select your hospital --</option>
                  {orgs.hospitals.map((h) => (
                    <option key={h.id} value={h.id}>
                      {h.code} — {h.name} ({h.area})
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>
        )}

        {/* WAREHOUSE ONBOARDING */}
        {role === 'warehouse' && (
          <div className="space-y-3 rounded-xl border border-amber-200/80 bg-amber-50/40 p-3.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-amber-900">
                Warehouse Hub Details
              </span>
              <div className="inline-flex rounded-lg border border-amber-200 bg-white p-0.5 text-[11px] font-semibold">
                <button
                  type="button"
                  onClick={() => setWarehouseMode('new')}
                  className={`rounded-md px-2.5 py-1 ${
                    warehouseMode === 'new' ? 'bg-amber-600 text-white' : 'text-slate-600'
                  }`}
                >
                  New Warehouse
                </button>
                <button
                  type="button"
                  onClick={() => setWarehouseMode('existing')}
                  className={`rounded-md px-2.5 py-1 ${
                    warehouseMode === 'existing' ? 'bg-amber-600 text-white' : 'text-slate-600'
                  }`}
                >
                  Join Existing
                </button>
              </div>
            </div>

            {warehouseMode === 'new' ? (
              <div className="space-y-3">
                <div>
                  <label className="mb-1 block text-[11px] font-semibold text-slate-700">
                    Warehouse Name
                  </label>
                  <input
                    required
                    value={newWarehouse.name}
                    onChange={(e) => setNewWarehouse({ ...newWarehouse, name: e.target.value })}
                    placeholder="e.g., Viman Nagar Cold-Chain Medical Hub"
                    className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                  />
                </div>

                <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
                  <div>
                    <label className="mb-1 block text-[11px] font-semibold text-slate-700">
                      Pune Area Quick-Pick
                    </label>
                    <select
                      value={
                        PUNE_AREA_PRESETS.some((p) => p.area === newWarehouse.area)
                          ? newWarehouse.area
                          : ''
                      }
                      onChange={(e) => applyPreset(e.target.value, 'warehouse')}
                      className="w-full rounded-lg border border-slate-300 bg-white px-2.5 py-2 text-xs"
                    >
                      <option value="">-- Pick locality (auto-fills GPS) --</option>
                      {PUNE_AREA_PRESETS.map((p) => (
                        <option key={p.area} value={p.area}>
                          {p.area}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="mb-1 block text-[11px] font-semibold text-slate-700">
                      Area / Locality Name
                    </label>
                    <input
                      required
                      value={newWarehouse.area}
                      onChange={(e) => setNewWarehouse({ ...newWarehouse, area: e.target.value })}
                      placeholder="e.g., Viman Nagar"
                      className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-2.5">
                  <div>
                    <label className="mb-1 block text-[11px] font-semibold text-slate-700">
                      Latitude
                    </label>
                    <input
                      type="number"
                      step="0.0001"
                      min="18.2"
                      max="18.9"
                      required
                      value={newWarehouse.latitude}
                      onChange={(e) =>
                        setNewWarehouse({ ...newWarehouse, latitude: e.target.value })
                      }
                      className="w-full rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-[11px] font-semibold text-slate-700">
                      Longitude
                    </label>
                    <input
                      type="number"
                      step="0.0001"
                      min="73.5"
                      max="74.2"
                      required
                      value={newWarehouse.longitude}
                      onChange={(e) =>
                        setNewWarehouse({ ...newWarehouse, longitude: e.target.value })
                      }
                      className="w-full rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-[11px] font-semibold text-slate-700">
                      Capacity (Units)
                    </label>
                    <input
                      type="number"
                      min="100"
                      required
                      value={newWarehouse.storage_capacity_units}
                      onChange={(e) =>
                        setNewWarehouse({
                          ...newWarehouse,
                          storage_capacity_units: e.target.value,
                        })
                      }
                      className="w-full rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs"
                    />
                  </div>
                </div>
              </div>
            ) : (
              <div>
                <label className="mb-1 block text-[11px] font-semibold text-slate-700">
                  Select Existing Warehouse
                </label>
                <select
                  required
                  disabled={loadingOrgs}
                  value={account.associated_warehouse_id}
                  onChange={(e) =>
                    setAccount({ ...account, associated_warehouse_id: e.target.value })
                  }
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs"
                >
                  <option value="">-- Select your warehouse --</option>
                  {orgs.warehouses.map((w) => (
                    <option key={w.id} value={w.id}>
                      {w.code} — {w.name} ({w.area})
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>
        )}

        {/* DELIVERY DRIVER & VEHICLE ONBOARDING */}
        {role === 'delivery' && (
          <div className="space-y-3 rounded-xl border border-emerald-200/80 bg-emerald-50/40 p-3.5">
            <span className="block text-xs font-bold uppercase tracking-wider text-emerald-900">
              Driver Fleet &amp; Vehicle Details
            </span>

            <div>
              <label className="mb-1 block text-[11px] font-semibold text-slate-700">
                Base Warehouse Depot
              </label>
              <select
                required
                disabled={loadingOrgs}
                value={newVehicle.warehouse_id}
                onChange={(e) => setNewVehicle({ ...newVehicle, warehouse_id: e.target.value })}
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs"
              >
                <option value="">-- Select home depot warehouse --</option>
                {orgs.warehouses.map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.code} — {w.name} ({w.area})
                  </option>
                ))}
              </select>
            </div>

            <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-3">
              <div>
                <label className="mb-1 block text-[11px] font-semibold text-slate-700">
                  Vehicle Type
                </label>
                <select
                  value={newVehicle.vehicle_type}
                  onChange={(e) => setNewVehicle({ ...newVehicle, vehicle_type: e.target.value })}
                  className="w-full rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs"
                >
                  <option value="medical_van">Medical Van</option>
                  <option value="cold_chain_truck">Cold-Chain Truck</option>
                  <option value="medical_truck">Medical Truck</option>
                </select>
              </div>
              <div>
                <label className="mb-1 block text-[11px] font-semibold text-slate-700">
                  Payload (kg)
                </label>
                <input
                  type="number"
                  min="100"
                  max="20000"
                  required
                  value={newVehicle.capacity_kg}
                  onChange={(e) => setNewVehicle({ ...newVehicle, capacity_kg: e.target.value })}
                  className="w-full rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs"
                />
              </div>
              <div>
                <label className="mb-1 block text-[11px] font-semibold text-slate-700">
                  Vehicle No. (Opt.)
                </label>
                <input
                  value={newVehicle.vehicle_code}
                  onChange={(e) => setNewVehicle({ ...newVehicle, vehicle_code: e.target.value })}
                  placeholder="MH12-MED-09"
                  className="w-full rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs"
                />
              </div>
            </div>
          </div>
        )}

        {/* Password Fields */}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-xs font-semibold text-slate-700">Password</label>
            <input
              type="password"
              required
              minLength={8}
              value={account.password}
              onChange={(e) => setAccount({ ...account, password: e.target.value })}
              placeholder="Min 8 characters"
              className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:border-sky-600 focus:outline-none"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold text-slate-700">
              Confirm Password
            </label>
            <input
              type="password"
              required
              minLength={8}
              value={account.confirm_password}
              onChange={(e) => setAccount({ ...account, confirm_password: e.target.value })}
              placeholder="Repeat password"
              className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:border-sky-600 focus:outline-none"
            />
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          {pwChecks.map((chk) => (
            <span
              key={chk.label}
              className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-medium ${
                chk.ok ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-500'
              }`}
            >
              <CheckCircle2 className="h-3 w-3" />
              {chk.label}
            </span>
          ))}
        </div>

        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-xl bg-teal-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {submitting ? 'Submitting Onboarding Registration...' : 'Submit for Admin Approval'}
        </button>
      </form>

      <div className="mt-5 border-t border-slate-100 pt-4 text-center text-sm text-slate-600">
        Already approved?{' '}
        <Link to="/login" className="font-semibold text-sky-700 hover:underline">
          Sign in
        </Link>
      </div>
    </AuthLayout>
  );
}
