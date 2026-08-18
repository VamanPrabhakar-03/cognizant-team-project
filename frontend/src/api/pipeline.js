import { request } from './client';

export const pipelineApi = {
  /** Upload a raw CMS claims ZIP — runs the full pipeline automatically. */
  uploadZip: (formData) =>
    request('/pipeline/upload', {
      method: 'POST',
      body: formData, // Handled automatically as multipart/form-data
    }),

  /** Legacy: send pre-normalized JSON claims batch. */
  ingestBatch: (payload) =>
    request('/pipeline/batches', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  getRunStatus: (runId) => request(`/pipeline/runs/${encodeURIComponent(runId)}`),
  resetData: () => request('/pipeline/reset', { method: 'POST' }),
};

