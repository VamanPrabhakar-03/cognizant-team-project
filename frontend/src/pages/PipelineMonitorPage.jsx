import React, { useState } from 'react';
import { pipelineApi } from '../api/index';
import { PageHeader } from '../components/common/PageHeader';
import { BatchUploadZone } from '../components/pipeline/BatchUploadZone';
import { PipelineStages } from '../components/pipeline/PipelineStages';
import { Badge } from '../components/common/Badge';
import { formatNumber } from '../utils/formatters';

export function PipelineMonitorPage({ onNavigate }) {
  const [isUploading, setIsUploading] = useState(false);
  const [lastRunResult, setLastRunResult] = useState(null);
  const [error, setError] = useState(null);

  const handleBatchUpload = async (uploadPayload) => {
    setIsUploading(true);
    setError(null);
    try {
      const res = await pipelineApi.ingestBatch(uploadPayload);
      setLastRunResult(res);
    } catch (err) {
      setError(err.message || 'Failed to process claims batch.');
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      {/* Page Header */}
      <PageHeader
        eyebrow="Data Operations & Ingestion"
        title="Pipeline Monitor"
        description="Real-time execution status of claims ingestion, crosswalk resolution, 8-signal scoring engine, and atomic evidence linking."
      />

      {error && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl text-rose-800 text-sm flex items-center gap-2 font-mono">
          <span className="material-symbols-outlined">error</span>
          <span>{error}</span>
        </div>
      )}

      {/* Main Grid: Upload Zone (Left) & Pipeline Stages (Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="lg:col-span-5 flex flex-col gap-6">
          <BatchUploadZone onUpload={handleBatchUpload} isUploading={isUploading} />
        </div>

        <div className="lg:col-span-7 flex flex-col gap-6">
          <PipelineStages
            currentStatus={lastRunResult ? lastRunResult.status : 'IDLE'}
            suspectsCount={lastRunResult ? lastRunResult.suspects : 0}
          />

          {/* Last Run Metrics Result Card */}
          {lastRunResult && (
            <div className="bg-surface-container-lowest rounded-2xl p-6 shadow-sm border border-outline-variant/20 flex flex-col gap-4">
              <div className="flex justify-between items-center">
                <div className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-emerald-600">task_alt</span>
                  <h4 className="font-manrope text-base font-bold text-on-surface">
                    Batch Execution Succeeded
                  </h4>
                </div>
                <Badge tone="success">{lastRunResult.status}</Badge>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="p-3 bg-surface rounded-xl border border-outline-variant/15 text-center">
                  <span className="font-mono text-[10px] text-on-surface-variant uppercase">Input Rows</span>
                  <p className="font-mono text-base font-bold text-on-surface mt-0.5">
                    {formatNumber(lastRunResult.input_rows)}
                  </p>
                </div>
                <div className="p-3 bg-surface rounded-xl border border-outline-variant/15 text-center">
                  <span className="font-mono text-[10px] text-on-surface-variant uppercase">Valid Claims</span>
                  <p className="font-mono text-base font-bold text-on-surface mt-0.5">
                    {formatNumber(lastRunResult.valid_rows)}
                  </p>
                </div>
                <div className="p-3 bg-surface rounded-xl border border-outline-variant/15 text-center">
                  <span className="font-mono text-[10px] text-on-surface-variant uppercase">Suspects</span>
                  <p className="font-mono text-base font-bold text-primary mt-0.5">
                    {formatNumber(lastRunResult.suspects)}
                  </p>
                </div>
                <div className="p-3 bg-surface rounded-xl border border-outline-variant/15 text-center">
                  <span className="font-mono text-[10px] text-on-surface-variant uppercase">Evidence Rows</span>
                  <p className="font-mono text-base font-bold text-tertiary mt-0.5">
                    {formatNumber(lastRunResult.evidence)}
                  </p>
                </div>
              </div>

              <div className="flex items-center justify-between pt-2 border-t border-outline-variant/15 text-xs font-mono text-on-surface-variant">
                <span>Run ID: {lastRunResult.run_id}</span>
                <button
                  onClick={() => onNavigate('suspects')}
                  className="text-primary font-bold hover:underline flex items-center gap-1"
                >
                  <span>View New Suspects in Queue</span>
                  <span className="material-symbols-outlined text-[16px]">arrow_forward</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
