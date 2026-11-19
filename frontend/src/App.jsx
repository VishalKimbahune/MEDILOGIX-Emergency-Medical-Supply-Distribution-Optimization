import React from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ToastProvider } from './components/common/ToastContext';
import ProtectedRoute from './components/auth/ProtectedRoute';
import RoleGuard from './components/auth/RoleGuard';
import MainLayout from './layouts/MainLayout';

// Auth & Public Pages
import Login from './pages/auth/Login';
import Register from './pages/auth/Register';
import ForgotPassword from './pages/auth/ForgotPassword';
import ResetPassword from './pages/auth/ResetPassword';
import PendingApproval from './pages/auth/PendingApproval';
import VerifyEmail from './pages/auth/VerifyEmail';
import Unauthorized from './pages/auth/Unauthorized';
import NotFound from './pages/auth/NotFound';

// Shared Authenticated Page
import Notifications from './pages/Notifications';

// Admin Portal Pages (Existing Phase 1–6 preserved + New Governance pages)
import Dashboard from './pages/Dashboard';
import Warehouses from './pages/Warehouses';
import Hospitals from './pages/Hospitals';
import Inventory from './pages/Inventory';
import Demands from './pages/Demands';
import Optimization from './pages/Optimization';
import RoutesPage from './pages/Routes';
import Scenarios from './pages/Scenarios';
import Analytics from './pages/Analytics';
import Settings from './pages/Settings';
import UsersManagement from './pages/admin/UsersManagement';
import VehiclesManagement from './pages/admin/VehiclesManagement';
import AuditLogs from './pages/admin/AuditLogs';

// Hospital Portal Pages
import HospitalDashboard from './pages/hospital/HospitalDashboard';
import HospitalCreateOrder from './pages/hospital/HospitalCreateOrder';
import HospitalOrders from './pages/hospital/HospitalOrders';
import HospitalProfile from './pages/hospital/HospitalProfile';

// Warehouse Portal Pages
import WarehouseDashboard from './pages/warehouse/WarehouseDashboard';
import WarehouseInventory from './pages/warehouse/WarehouseInventory';
import WarehouseShipments from './pages/warehouse/WarehouseShipments';
import WarehouseProfile from './pages/warehouse/WarehouseProfile';

// Delivery Portal Pages
import DeliveryDashboard from './pages/delivery/DeliveryDashboard';
import DeliveryAssignments from './pages/delivery/DeliveryAssignments';
import DeliveryHistory from './pages/delivery/DeliveryHistory';
import DeliveryProfile from './pages/delivery/DeliveryProfile';

function SmartHomeRedirect() {
  const { user, loading, getPortalHome } = useAuth();
  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 text-sm font-medium text-slate-500">
        Loading MEDILOGIX...
      </div>
    );
  }
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  return <Navigate to={getPortalHome(user.role)} replace />;
}

export default function App() {
  return (
    <ToastProvider>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            {/* Public Auth Routes */}
            <Route path="/" element={<SmartHomeRedirect />} />
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route path="/forgot-password" element={<ForgotPassword />} />
            <Route path="/reset-password" element={<ResetPassword />} />
            <Route path="/pending-approval" element={<PendingApproval />} />
            <Route path="/verify-email" element={<VerifyEmail />} />
            <Route path="/unauthorized" element={<Unauthorized />} />

            {/* Admin Portal (/admin/*) */}
            <Route
              path="/admin"
              element={
                <ProtectedRoute>
                  <RoleGuard allowedRoles={['admin']}>
                    <MainLayout />
                  </RoleGuard>
                </ProtectedRoute>
              }
            >
              <Route index element={<Navigate to="/admin/dashboard" replace />} />
              <Route path="dashboard" element={<Dashboard />} />
              <Route path="warehouses" element={<Warehouses />} />
              <Route path="hospitals" element={<Hospitals />} />
              <Route path="inventory" element={<Inventory />} />
              <Route path="demands" element={<Demands />} />
              <Route path="optimization" element={<Optimization />} />
              <Route path="routes" element={<RoutesPage />} />
              <Route path="scenarios" element={<Scenarios />} />
              <Route path="analytics" element={<Analytics />} />
              <Route path="users" element={<UsersManagement />} />
              <Route path="vehicles" element={<VehiclesManagement />} />
              <Route path="audit-logs" element={<AuditLogs />} />
              <Route path="notifications" element={<Notifications />} />
              <Route path="settings" element={<Settings />} />
            </Route>

            {/* Hospital Portal (/hospital/*) */}
            <Route
              path="/hospital"
              element={
                <ProtectedRoute>
                  <RoleGuard allowedRoles={['hospital']}>
                    <MainLayout />
                  </RoleGuard>
                </ProtectedRoute>
              }
            >
              <Route index element={<Navigate to="/hospital/dashboard" replace />} />
              <Route path="dashboard" element={<HospitalDashboard />} />
              <Route path="orders/new" element={<HospitalCreateOrder />} />
              <Route path="orders" element={<HospitalOrders />} />
              <Route path="notifications" element={<Notifications />} />
              <Route path="profile" element={<HospitalProfile />} />
            </Route>

            {/* Warehouse Portal (/warehouse/*) */}
            <Route
              path="/warehouse"
              element={
                <ProtectedRoute>
                  <RoleGuard allowedRoles={['warehouse']}>
                    <MainLayout />
                  </RoleGuard>
                </ProtectedRoute>
              }
            >
              <Route index element={<Navigate to="/warehouse/dashboard" replace />} />
              <Route path="dashboard" element={<WarehouseDashboard />} />
              <Route path="inventory" element={<WarehouseInventory />} />
              <Route path="shipments" element={<WarehouseShipments />} />
              <Route path="notifications" element={<Notifications />} />
              <Route path="profile" element={<WarehouseProfile />} />
            </Route>

            {/* Delivery Portal (/delivery/*) */}
            <Route
              path="/delivery"
              element={
                <ProtectedRoute>
                  <RoleGuard allowedRoles={['delivery']}>
                    <MainLayout />
                  </RoleGuard>
                </ProtectedRoute>
              }
            >
              <Route index element={<Navigate to="/delivery/dashboard" replace />} />
              <Route path="dashboard" element={<DeliveryDashboard />} />
              <Route path="assignments" element={<DeliveryAssignments />} />
              <Route path="history" element={<DeliveryHistory />} />
              <Route path="notifications" element={<Notifications />} />
              <Route path="profile" element={<DeliveryProfile />} />
            </Route>

            {/* 404 Fallback */}
            <Route path="*" element={<NotFound />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ToastProvider>
  );
}
