import api from './api';

export async function fetchNotifications(params = {}) {
  const { data } = await api.get('/notifications', { params });
  return data;
}

export async function fetchUnreadNotificationCount() {
  const { data } = await api.get('/notifications/unread-count');
  return data;
}

export async function markNotificationRead(notificationId) {
  const { data } = await api.patch(`/notifications/${notificationId}/read`);
  return data;
}

export async function markAllNotificationsRead() {
  const { data } = await api.post('/notifications/read-all');
  return data;
}
