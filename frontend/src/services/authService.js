import api, { clearAccessToken, setAccessToken } from './api';

export async function fetchPublicOrganizations() {
  const { data } = await api.get('/auth/public-organizations');
  return data;
}

export async function registerUser(payload) {
  const { data } = await api.post('/auth/register', payload);
  return data;
}

export async function loginUser(email, password) {
  const { data } = await api.post('/auth/login', { email, password });
  if (data?.access_token) {
    setAccessToken(data.access_token);
  }
  return data;
}

export async function refreshSession() {
  const { data } = await api.post(
    '/auth/refresh',
    {},
    {
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
      },
    }
  );
  if (data?.access_token) {
    setAccessToken(data.access_token);
  }
  return data;
}

export async function logoutUser() {
  try {
    await api.post('/auth/logout', {});
  } finally {
    clearAccessToken();
  }
}

export async function fetchCurrentUser() {
  const { data } = await api.get('/auth/me');
  return data;
}

export async function updateCurrentProfile(payload) {
  const { data } = await api.patch('/auth/me', payload);
  return data;
}

export async function forgotPassword(email) {
  const { data } = await api.post('/auth/forgot-password', { email });
  return data;
}

export async function resetPassword(payload) {
  const { data } = await api.post('/auth/reset-password', payload);
  return data;
}

export async function verifyEmail(token) {
  const { data } = await api.post('/auth/verify-email', { token });
  return data;
}
