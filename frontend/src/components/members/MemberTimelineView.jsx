import React from 'react';
import { Badge } from '../common/Badge';
import { formatDate } from '../../utils/formatters';

export function MemberTimelineView({
  events = [],
  selectedYear = '',
  onSelectYear,
  hccOnly = false,
  onToggleHccOnly,
}) {
  const years = ['', '2023', '2022', '2021', '2020'];

  return (
    <div className="flex flex-col gap-4">
      {/* Timeline Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-3 bg-surface-container-low rounded-xl border border-outline-variant/20">
        <div className="flex items-center gap-1">
          {years.map((y) => (
            <button
              key={y}
              onClick={() => onSelectYear(y)}
              className={`px-3 py-1.5 rounded-lg text-xs font-mono font-semibold transition-all ${
                selectedYear === y
                  ? 'bg-primary text-on-primary shadow-xs'
                  : 'text-on-surface-variant hover:bg-surface-container-high'
              }`}
            >
              {y === '' ? 'All Years' : y}
            </button>
          ))}
        </div>

        <label className="flex items-center gap-2 text-xs font-mono text-on-surface cursor-pointer select-none">
          <input
            type="checkbox"
            checked={hccOnly}
            onChange={(e) => onToggleHccOnly(e.target.checked)}
            className="rounded text-primary focus:ring-primary"
          />
          <span>Mapped HCC Events Only</span>
        </label>
      </div>

      {/* Events Stream */}
      {events.length === 0 ? (
        <div className="text-center py-8 text-on-surface-variant text-sm font-mono bg-surface rounded-xl border border-outline-variant/20">
          No medical events recorded for this selection.
        </div>
      ) : (
        <div className="relative pl-6 before:absolute before:top-2 before:bottom-2 before:left-[11px] before:w-[2px] before:bg-outline-variant/30 flex flex-col gap-4">
          {events.map((evt, idx) => {
            const isDx = (evt.event_type || '').toLowerCase() === 'diagnosis';
            const isRx = (evt.event_type || '').toLowerCase() === 'prescription';
            const hasHcc = evt.hcc_v28 && String(evt.hcc_v28).trim() !== '';

            let iconName = 'event_note';
            let iconBg = 'bg-primary text-on-primary';
            if (isRx) {
              iconName = 'medication';
              iconBg = 'bg-tertiary text-on-tertiary';
            } else if (evt.is_principal) {
              iconName = 'stars';
              iconBg = 'bg-error text-on-error';
            }

            return (
              <div key={evt.id || evt.event_id || idx} className="relative flex items-start gap-4 group">
                {/* Timeline Dot */}
                <div
                  className={`w-6 h-6 rounded-full ${iconBg} flex items-center justify-center -ml-[23px] shadow-xs ring-4 ring-background flex-shrink-0`}
                >
                  <span className="material-symbols-outlined text-[14px]">{iconName}</span>
                </div>

                {/* Event Card */}
                <div className="flex-1 bg-surface-container-lowest p-4 rounded-xl border border-outline-variant/20 shadow-xs hover:shadow-sm transition-shadow">
                  <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-bold text-on-surface">
                        {formatDate(evt.event_date)}
                      </span>
                      <Badge tone={isRx ? 'pink' : 'violet'}>
                        {evt.source || (isRx ? 'PART D' : 'CLAIM')}
                      </Badge>
                      {evt.is_principal && (
                        <Badge tone="error" icon="star">
                          Principal Dx
                        </Badge>
                      )}
                    </div>

                    {hasHcc && (
                      <span className="font-mono text-xs font-bold text-primary bg-primary/10 px-2 py-0.5 rounded">
                        HCC {evt.hcc_v28}
                      </span>
                    )}
                  </div>

                  <div className="flex flex-col gap-0.5 text-sm text-on-surface">
                    <div className="font-mono text-xs font-semibold text-primary">
                      {evt.code || evt.drug_code || '—'}
                    </div>
                    <div className="text-xs text-on-surface-variant">
                      {isRx
                        ? `Part D Pharmacy Fill (NDC: ${evt.drug_code || '—'})`
                        : `Clinical Diagnosis encounter${evt.claim_id ? ` · Claim ID ${evt.claim_id}` : ''}`}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
