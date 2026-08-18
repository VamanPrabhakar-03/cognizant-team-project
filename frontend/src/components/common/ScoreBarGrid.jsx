import React from 'react';
import { formatPercent } from '../../utils/formatters';

const DIMENSIONS = [
  { key: 'recency_score', label: 'Recency Signal', weight: '15%', icon: 'schedule' },
  { key: 'frequency_score', label: 'Frequency Volume', weight: '18%', icon: 'repeat' },
  { key: 'persistence_score', label: 'Persistence (Months)', weight: '18%', icon: 'date_range' },
  { key: 'repeated_claim_score', label: 'Repeated Claims', weight: '15%', icon: 'receipt_long' },
  { key: 'repeated_date_score', label: 'Distinct Service Dates', weight: '15%', icon: 'event_repeat' },
  { key: 'source_diversity_score', label: 'Source Diversity', weight: '8%', icon: 'domain' },
  { key: 'principal_score', label: 'Principal Diagnosis', weight: '8%', icon: 'stars' },
  { key: 'prescription_score', label: 'Rx Part D Alignment', weight: '3%', icon: 'medication' },
];

export function ScoreBarGrid({ suspect = {}, className = '' }) {
  return (
    <div className={`grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 ${className}`}>
      {DIMENSIONS.map(({ key, label, weight, icon }) => {
        const val = Number(suspect[key] || 0);
        const percent = Math.min(100, Math.max(0, Math.round(val * 100)));

        let barColor = 'bg-primary';
        if (percent >= 75) barColor = 'bg-primary';
        else if (percent >= 40) barColor = 'bg-secondary';
        else barColor = 'bg-outline/50';

        return (
          <div
            key={key}
            className="bg-surface p-3.5 rounded-xl border border-outline-variant/20 flex flex-col justify-between gap-2 shadow-sm hover:shadow transition-shadow"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5 min-w-0">
                <span className="material-symbols-outlined text-[16px] text-primary/70">{icon}</span>
                <span className="font-mono text-[11px] text-on-surface-variant font-medium truncate">{label}</span>
              </div>
              <span className="font-mono text-[10px] text-outline font-semibold">{weight}</span>
            </div>

            <div className="flex items-end justify-between mt-1">
              <span className="font-manrope text-base font-bold text-on-surface">
                {formatPercent(val)}
              </span>
              <div className="flex items-center gap-0.5">
                {[1, 2, 3].map((step) => {
                  const active = (percent >= 75 && step <= 3) || (percent >= 40 && step <= 2) || (percent > 0 && step <= 1);
                  return (
                    <div
                      key={step}
                      className={`w-1.5 h-3.5 rounded-xs transition-colors ${
                        active ? barColor : 'bg-surface-dim'
                      }`}
                    />
                  );
                })}
              </div>
            </div>

            <div className="w-full bg-surface-container-high h-1.5 rounded-full overflow-hidden">
              <div
                className={`h-full ${barColor} transition-all duration-500 rounded-full`}
                style={{ width: `${percent}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
