import React from 'react';
import { formatNumber } from '../../utils/formatters';

export function PriorityBreakdown({ scores = { high: 0, medium: 0, low: 0 }, pendingCount = 0, onOpenQueue }) {
  const total = (scores.high || 0) + (scores.medium || 0) + (scores.low || 0) || 1;

  const tiers = [
    { label: 'High Priority (≥ 0.75)', value: scores.high || 0, color: 'bg-error', text: 'text-error', dot: 'bg-error' },
    { label: 'Medium Priority (0.50–0.74)', value: scores.medium || 0, color: 'bg-primary', text: 'text-primary', dot: 'bg-primary' },
    { label: 'Low Priority (< 0.50)', value: scores.low || 0, color: 'bg-outline', text: 'text-outline', dot: 'bg-outline' },
  ];

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* Priority Progress Breakdown */}
      <div className="lg:col-span-2 bg-surface-container-lowest rounded-2xl p-6 shadow-sm border border-outline-variant/20 flex flex-col justify-between">
        <div className="flex justify-between items-center mb-4">
          <div>
            <span className="font-mono text-xs font-semibold text-primary uppercase tracking-wider">
              Stratification
            </span>
            <h3 className="font-manrope text-xl font-bold text-on-surface">
              Confidence & Priority Distribution
            </h3>
          </div>
          <span className="font-mono text-xs text-on-surface-variant font-medium">
            {formatNumber(total)} Total Suspects
          </span>
        </div>

        <div className="flex flex-col gap-4 my-2">
          {tiers.map((tier) => {
            const pct = Math.round((tier.value / total) * 100);
            return (
              <div key={tier.label} className="flex flex-col gap-1.5">
                <div className="flex justify-between items-center text-sm">
                  <div className="flex items-center gap-2">
                    <span className={`w-2.5 h-2.5 rounded-full ${tier.dot}`} />
                    <span className="font-medium text-on-surface">{tier.label}</span>
                  </div>
                  <div className="flex items-baseline gap-2 font-mono">
                    <span className="font-bold text-on-surface">{formatNumber(tier.value)}</span>
                    <span className="text-xs text-on-surface-variant">({pct}%)</span>
                  </div>
                </div>
                <div className="w-full bg-surface-container-high h-2.5 rounded-full overflow-hidden">
                  <div
                    className={`h-full ${tier.color} transition-all duration-700 rounded-full`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>

        <div className="mt-4 pt-3 border-t border-outline-variant/15 flex items-center justify-between text-xs text-on-surface-variant font-mono">
          <span>Formula: 8-Signal Weighted Clinical Score</span>
          <span className="text-primary font-semibold">Deterministic & Auditable</span>
        </div>
      </div>

      {/* Action Prompt Card */}
      <div className="bg-gradient-to-br from-primary-container to-primary text-on-primary rounded-2xl p-6 shadow-md flex flex-col justify-between relative overflow-hidden">
        <div className="relative z-10">
          <span className="font-mono text-xs uppercase tracking-widest text-on-primary-container">
            Action Required
          </span>
          <h3 className="font-manrope text-2xl font-extrabold mt-1">
            {formatNumber(pendingCount)} Pending Reviews
          </h3>
          <p className="text-sm text-on-primary/90 mt-2 leading-relaxed">
            Review the highest-scoring emerging and recapture opportunities first to ensure audit readiness for CMS V28.
          </p>
        </div>

        <div className="mt-6 relative z-10">
          <button
            onClick={onOpenQueue}
            className="w-full py-3 px-4 bg-surface text-primary font-manrope font-bold text-sm rounded-xl shadow hover:bg-surface-container-low transition-all flex items-center justify-center gap-2 group"
          >
            <span>Open Suspect Triage Queue</span>
            <span className="material-symbols-outlined text-[18px] group-hover:translate-x-1 transition-transform">
              arrow_forward
            </span>
          </button>
        </div>

        <div className="absolute -right-8 -bottom-8 w-36 h-36 bg-white/10 rounded-full blur-xl pointer-events-none" />
      </div>
    </div>
  );
}
