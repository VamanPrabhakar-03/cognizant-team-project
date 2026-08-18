import { request } from './client';

export const reviewsApi = {
  list: (params = '') => {
    const q = typeof params === 'object'
      ? `?${new URLSearchParams(params).toString()}`
      : (params.startsWith('?') || params === '' ? params : `?${params}`);
    return request(`/reviews${q}`);
  },
  getStats: () => request('/reviews/stats'),
  createDecision: (payload) =>
    request('/reviews', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
};
