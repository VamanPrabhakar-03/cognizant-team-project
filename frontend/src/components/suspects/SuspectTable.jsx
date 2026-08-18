import React from 'react';
import { Badge } from '../common/Badge';
import { formatNumber, formatScore, getPriorityColor, getPriorityTier } from '../../utils/formatters';

export function SuspectTable({
  items = [],
  onSelectSuspect,
  onQuickReview = null,
  isLoading = false,
}) {
  if (items.length === 0 && !isLoading) {
    return null;
  }

  return (
    <div className="bg-surface-container-lowest rounded-2xl shadow-sm border border-outline-variant/20 overflow-hidden flex flex-col">
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-surface-container-low text-on-surface-variant border-b border-outline-variant/20 font-mono text-xs uppercase tracking-wider">
              <th className="p-4 font-semibold whitespace-nowrap">Member ID</th>
              <th className="p-4 font-semibold whitespace-nowrap">HCC Code</th>
              <th className="p-4 font-semibold whitespace-nowrap">Gap Type</th>
              <th className="p-4 font-semibold whitespace-nowrap">ML Review Score</th>
              <th className="p-4 font-semibold whitespace-nowrap">ML Priority</th>
              <th className="p-4 font-semibold whitespace-nowrap text-center">Evidence Events</th>
              <th className="p-4 font-semibold whitespace-nowrap">Latest Date</th>
              <th className="p-4 font-semibold whitespace-nowrap">Status</th>
              <th className="p-4 font-semibold whitespace-nowrap text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-outline-variant/15 text-sm">
            {items.map((item) => {
              const score = item.ml_priority_score ?? item.priority_score ?? 0;
              const scorePercent = formatScore(score);
              const tier = item.ml_priority || item.priority || getPriorityTier(score);
              const isEmerging = (item.suspect_type || item.gap_type || '').toUpperCase() === 'EMERGING';
              const isReviewed = item.status === 'REVIEWED';

              return (
                <tr
                  key={item.suspect_id}
                  onClick={() => onSelectSuspect(item.suspect_id)}
                  className="hover:bg-surface-container-low/70 transition-colors group cursor-pointer"
                >
                  {/* Member ID */}
                  <td className="p-4 font-mono font-bold text-primary group-hover:underline">
                    {item.bene_id}
                  </td>

                  {/* HCC Category */}
                  <td className="p-4">
                    <div className="flex flex-col">
                      <span className="font-mono font-bold text-on-surface">
                        HCC {item.hcc_v28}
                      </span>
                      <span className="text-xs text-on-surface-variant truncate max-w-xs">
                        {item.hcc_description || 'Documentation Opportunity'}
                      </span>
                    </div>
                  </td>

                  {/* Gap Type */}
                  <td className="p-4">
                    <Badge tone={isEmerging ? 'pink' : 'violet'}>
                      {item.suspect_type || item.gap_type || 'EMERGING'}
                    </Badge>
                  </td>

                  {/* Priority Score Bar */}
                  <td className="p-4">
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-bold text-on-surface w-8">
                        {scorePercent}
                      </span>
                      <div className="w-20 bg-surface-container-high h-2 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all ${
                            tier === 'HIGH' ? 'bg-error' : tier === 'MEDIUM' ? 'bg-primary' : 'bg-outline'
                          }`}
                          style={{ width: `${scorePercent}%` }}
                        />
                      </div>
                    </div>
                  </td>

                  {/* Priority Tier */}
                  <td className="p-4">
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-mono font-semibold border ${
                        tier === 'HIGH'
                          ? 'bg-error-container/60 text-error border-error/30'
                          : tier === 'MEDIUM'
                          ? 'bg-secondary-container/30 text-secondary border-secondary/30'
                          : 'bg-surface-container-high text-outline border-outline/20'
                      }`}
                    >
                      {tier}{item.ml_review_rank ? ` · #${item.ml_review_rank}` : ''}
                    </span>
                  </td>

                  {/* Evidence Count */}
                  <td className="p-4 text-center font-mono font-semibold text-on-surface">
                    {item.evidence_count || item.diagnosis_count || 1}
                  </td>

                  {/* Latest Evidence Date */}
                  <td className="p-4 font-mono text-xs text-on-surface-variant">
                    {item.last_evidence_date || item.first_evidence_date || '—'}
                  </td>

                  {/* Status */}
                  <td className="p-4">
                    <Badge tone={isReviewed ? 'success' : 'slate'}>
                      {item.status || 'PENDING_REVIEW'}
                    </Badge>
                  </td>

                  {/* Open Arrow */}
                  <td className="p-4 text-right">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectSuspect(item.suspect_id);
                      }}
                      className="p-1.5 rounded-lg text-outline hover:text-primary hover:bg-surface-container transition-all group-hover:translate-x-1"
                    >
                      <span className="material-symbols-outlined text-[20px]">chevron_right</span>
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
