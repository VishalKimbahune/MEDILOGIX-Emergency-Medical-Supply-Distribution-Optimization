import React from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { ToastProvider } from './components/common/ToastContext';
import MainLayout from './layouts/MainLayout';
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

export default function App() {
  return (
    <ToastProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<MainLayout />}>
            <Route index element={<Dashboard />} />
            <Route path="warehouses" element={<Warehouses />} />
            <Route path="hospitals" element={<Hospitals />} />
            <Route path="inventory" element={<Inventory />} />
            <Route path="demands" element={<Demands />} />
            <Route path="optimization" element={<Optimization />} />
            <Route path="routes" element={<RoutesPage />} />
            <Route path="scenarios" element={<Scenarios />} />
            <Route path="analytics" element={<Analytics />} />
            <Route path="settings" element={<Settings />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ToastProvider>
  );
}
