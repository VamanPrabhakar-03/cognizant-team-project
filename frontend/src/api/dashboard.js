import { request } from './client';

export const dashboardApi = {
  getMetrics: () => request('/dashboard/metrics'),
  getScoreDistribution: () => request('/dashboard/score-distribution'),
  getHccDistribution: () => request('/dashboard/hcc-distribution'),
  getOverview: async () => {
    const [metrics, scores, hccs] = await Promise.all([
      request('/dashboard/metrics'),
      request('/dashboard/score-distribution'),
      request('/dashboard/hcc-distribution'),
    ]);
    return { metrics, scores, hccs };
  },
};
