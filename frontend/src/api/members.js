import { request } from './client';

export const membersApi = {
  list: (params = '') => {
    const q = typeof params === 'object'
      ? `?${new URLSearchParams(params).toString()}`
      : (params.startsWith('?') || params === '' ? params : `?${params}`);
    return request(`/members${q}`);
  },
  getById: (beneId) => request(`/members/${encodeURIComponent(beneId)}`),
  getTimeline: (beneId, params = '') => {
    const q = typeof params === 'object'
      ? `?${new URLSearchParams(params).toString()}`
      : (params.startsWith('?') || params === '' ? params : `?${params}`);
    return request(`/members/${encodeURIComponent(beneId)}/timeline${q}`);
  },
};
