import { request } from './client';

export const suspectsApi = {
  list: (params = '') => {
    const q = typeof params === 'object' 
      ? `?${new URLSearchParams(params).toString()}`
      : (params.startsWith('?') || params === '' ? params : `?${params}`);
    return request(`/suspects${q}`);
  },
  getById: (suspectId) => request(`/suspects/${encodeURIComponent(suspectId)}`),
  updateStatus: (suspectId, status) =>
    request(`/suspects/${encodeURIComponent(suspectId)}`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    }),
};
