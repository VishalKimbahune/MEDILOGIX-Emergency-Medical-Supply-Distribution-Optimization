import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { clearAccessToken, registerAuthFailureHandler } from '../services/api';
import {
  fetchCurrentUser,
  loginUser,
  logoutUser,
  refreshSession,
} from '../services/authService';

const AuthContext = createContext(null);

export function getPortalHomeForRole(role) {
  switch (role) {
    case 'admin':
      return '/admin/dashboard';
    case 'hospital':
      return '/hospital/dashboard';
    case 'warehouse':
      return '/warehouse/dashboard';
    case 'delivery':
      return '/delivery/dashboard';
    default:
      return '/login';
  }
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const handleSessionCleared = useCallback(() => {
    clearAccessToken();
    setUser(null);
  }, []);

  useEffect(() => {
    registerAuthFailureHandler(handleSessionCleared);
    return () => registerAuthFailureHandler(null);
  }, [handleSessionCleared]);

  // Restore session silently via HTTP-only refresh cookie on initial app load
  useEffect(() => {
    let mounted = true;
    async function restoreSession() {
      try {
        const data = await refreshSession();
        if (mounted && data?.user) {
          setUser(data.user);
        }
      } catch {
        if (mounted) {
          clearAccessToken();
          setUser(null);
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }
    restoreSession();
    return () => {
      mounted = false;
    };
  }, []);

  const login = useCallback(async (email, password) => {
    const data = await loginUser(email, password);
    setUser(data.user);
    return data.user;
  }, []);

  const logout = useCallback(async () => {
    await logoutUser();
    setUser(null);
  }, []);

  const refreshProfile = useCallback(async () => {
    const me = await fetchCurrentUser();
    setUser(me);
    return me;
  }, []);

  const value = useMemo(
    () => ({
      user,
      loading,
      isAuthenticated: Boolean(user),
      login,
      logout,
      refreshProfile,
      getPortalHome: getPortalHomeForRole,
    }),
    [user, loading, login, logout, refreshProfile]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return ctx;
}
