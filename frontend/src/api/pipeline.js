import { request } from './client';

export const pipelineApi = {
  ingestBatch: (payload) =>
    request('/pipeline/batches', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  getRunStatus: (runId) => request(`/pipeline/runs/${encodeURIComponent(runId)}`),
};
