import React, { useEffect, useState } from 'react';
import { dashboardApi } from '../api/index';
import { PageHeader } from '../components/common/PageHeader';
import { MetricCard } from '../components/common/MetricCard';
import { PriorityBreakdown } from '../components/dashboard/PriorityBreakdown';
import { HCCDistributionChart } from '../components/dashboard/HCCDistributionChart';
import { LoadingSpinner } from '../components/common/LoadingSpinner';

export function DashboardPage({ onNavigate }) {
  const [data, setData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await dashboardApi.getOverview();
      setData(res);
    } catch (err) {
      setError(err.message || 'Failed to load executive risk dashboard data.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  if (isLoading) {
    return <LoadingSpinner message="Aggregating clinical risk intelligence & metrics..." />;
  }

  const metrics = data?.metrics || {};
  const scores = data?.scores || { high: 0, medium: 0, low: 0 };
  const hccs = data?.hccs || [];

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <PageHeader
        eyebrow="Clinical Intelligence Overview"
        title="Executive Risk Dashboard"
        description="Real-time overview of risk adjustment performance, pipeline operations, and HCC suspect generation across the member population."
        actions={
          <div className="flex items-center gap-3">
            <button
              onClick={loadData}
              className="px-4 py-2 bg-surface-container text-on-surface font-manrope font-semibold text-xs rounded-xl hover:bg-surface-container-high transition-colors flex items-center gap-1.5"
            >
              <span className="material-symbols-outlined text-[18px]">refresh</span>
              <span>Refresh</span>
            </button>
            <button
              onClick={() => onNavigate('pipeline')}
              className="px-4 py-2 bg-primary text-on-primary font-manrope font-bold text-xs rounded-xl shadow hover:bg-primary/90 transition-all flex items-center gap-1.5"
            >
              <span className="material-symbols-outlined text-[18px]">upload_file</span>
              <span>New Claims Batch</span>
            </button>
          </div>
        }
      />

      {error && (
        <div className="p-4 bg-amber-50 border border-amber-200 rounded-xl text-amber-800 text-sm flex items-center gap-2 font-mono">
          <span className="material-symbols-outlined">warning</span>
          <span>{error}</span>
        </div>
      )}

      {/* Top 4 KPI Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        <MetricCard
          label="Total Beneficiaries"
          value={metrics.total_members || 0}
          helper={`${metrics.members_with_baseline || 0} with 2021-22 Baseline`}
          icon="group"
          trend="+2.4%"
        />
        <MetricCard
          label="Claims Processed"
          value={metrics.claims_processed || 0}
          helper="Evaluated in 2023 temporal window"
          icon="receipt_long"
          trend="+8.1%"
        />
        <MetricCard
          label="Pipeline Runs"
          value={metrics.pipeline_runs || 0}
          helper="Tracked batch executions"
          icon="route"
          trend="MTD"
        />
        <MetricCard
          label="Total HCC Suspects"
          value={metrics.total_suspects || 0}
          helper={`${metrics.pending_count || 0} pending review`}
          icon="warning"
          tone="tertiary"
          trend="+12%"
        />
      </div>

      {/* Stratification & Pending Action */}
      <PriorityBreakdown
        scores={scores}
        pendingCount={metrics.pending_count || 0}
        onOpenQueue={() => onNavigate('suspects')}
      />

      {/* HCC Categories Distribution Chart */}
      <HCCDistributionChart
        items={hccs}
        onSelectHcc={(hcc) => onNavigate(`suspects?search=${hcc}`)}
      />

      {/* System Workflow Steps */}
      <div className="bg-surface-container-lowest rounded-2xl p-6 shadow-sm border border-outline-variant/20">
        <div className="flex justify-between items-center mb-4">
          <div>
            <span className="font-mono text-xs font-semibold text-primary uppercase tracking-wider">
              Architecture
            </span>
            <h3 className="font-manrope text-lg font-bold text-on-surface">
              End-to-End System Workflow
            </h3>
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-4 bg-surface rounded-xl border border-outline-variant/20">
            <span className="font-mono text-xs text-primary font-bold">01 · INTAKE</span>
            <h4 className="font-manrope font-bold text-sm text-on-surface mt-1">Incremental Ingestion</h4>
            <p className="text-xs text-on-surface-variant mt-1">
              New claim batches are validated and linked with member baseline profiles.
            </p>
          </div>
          <div className="p-4 bg-surface rounded-xl border border-outline-variant/20">
            <span className="font-mono text-xs text-primary font-bold">02 · SCORING</span>
            <h4 className="font-manrope font-bold text-sm text-on-surface mt-1">8-Signal Suspect Engine</h4>
            <p className="text-xs text-on-surface-variant mt-1">
              Evaluates recency, frequency, persistence, repeated claims, source diversity, and Part D Rx support.
            </p>
          </div>
          <div className="p-4 bg-surface rounded-xl border border-outline-variant/20">
            <span className="font-mono text-xs text-primary font-bold">03 · REVIEW</span>
            <h4 className="font-manrope font-bold text-sm text-on-surface mt-1">Human-in-the-Loop Triage</h4>
            <p className="text-xs text-on-surface-variant mt-1">
              Reviewers examine transparent atomic claim evidence and submit compliance decisions.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
