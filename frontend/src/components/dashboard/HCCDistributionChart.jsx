import React from 'react';
import { formatNumber } from '../../utils/formatters';

export function HCCDistributionChart({ items = [], onSelectHcc = null }) {
  const topItems = items.slice(0, 8);
  const maxVal = Math.max(
    ...topItems.map((i) => (i.emerging_count || 0) + (i.recapture_count || 0)),
    1
  );

  return (
    <div className="bg-surface-container-lowest rounded-2xl p-6 shadow-sm border border-outline-variant/20 flex flex-col justify-between">
      <div className="flex justify-between items-center mb-6">
        <div>
          <span className="font-mono text-xs font-semibold text-primary uppercase tracking-wider">
            Category Breakdown
          </span>
          <h3 className="font-manrope text-xl font-bold text-on-surface">
            Top CMS-HCC V28 Categories
          </h3>
        </div>
        <div className="flex items-center gap-4 text-xs font-mono">
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-sm bg-tertiary" />
            <span>Emerging</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-sm bg-primary" />
            <span>Recapture</span>
          </div>
        </div>
      </div>

      {topItems.length === 0 ? (
        <div className="text-center py-10 text-on-surface-variant text-sm font-mono">
          No HCC distribution data available.
        </div>
      ) : (
        <div className="flex flex-col gap-3.5">
          {topItems.map((item) => {
            const emerging = item.emerging_count || 0;
            const recapture = item.recapture_count || 0;
            const total = emerging + recapture;
            const emergingPct = Math.round((emerging / maxVal) * 100);
            const recapturePct = Math.round((recapture / maxVal) * 100);

            return (
              <div
                key={item.hcc_v28}
                onClick={() => onSelectHcc && onSelectHcc(item.hcc_v28)}
                className="group cursor-pointer p-2 rounded-xl hover:bg-surface-container-low transition-colors"
              >
                <div className="flex justify-between items-center text-xs mb-1.5">
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-bold text-primary bg-primary/10 px-2 py-0.5 rounded">
                      HCC {item.hcc_v28}
                    </span>
                    <span className="font-medium text-on-surface truncate max-w-xs md:max-w-md">
                      {item.description || `HCC ${item.hcc_v28}`}
                    </span>
                  </div>
                  <span className="font-mono font-bold text-on-surface">
                    {formatNumber(total)}
                  </span>
                </div>

                <div className="w-full bg-surface-container-high h-2.5 rounded-full overflow-hidden flex">
                  <div
                    className="h-full bg-tertiary transition-all duration-500"
                    style={{ width: `${emergingPct}%` }}
                    title={`Emerging: ${emerging}`}
                  />
                  <div
                    className="h-full bg-primary transition-all duration-500"
                    style={{ width: `${recapturePct}%` }}
                    title={`Recapture: ${recapture}`}
                  />
                </div>
              </div>
            );
          })}
        </div>
      )}

      <div className="mt-4 pt-3 border-t border-outline-variant/15 text-xs text-on-surface-variant flex justify-between font-mono">
        <span>Showing top {topItems.length} categories by suspect volume</span>
        <span>CMS-HCC V28 Payment 2026</span>
      </div>
    </div>
  );
}
