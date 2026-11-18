import { useEffect, useState } from 'react';
import { fetchHealthStatus } from '../services/api';

export function useApiHealth() {
  const [health, setHealth] = useState(null);
  const [status, setStatus] = useState('checking'); // checking | online | offline

  useEffect(() => {
    let active = true;
    async function check() {
      try {
        const data = await fetchHealthStatus();
        if (active) {
          setHealth(data);
          setStatus(data.status === 'healthy' ? 'online' : 'degraded');
        }
      } catch {
        if (active) {
          setHealth(null);
          setStatus('offline');
        }
      }
    }
    check();
    return () => {
      active = false;
    };
  }, []);

  return { health, status };
}
