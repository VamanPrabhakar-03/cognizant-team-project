import React from 'react';

const STAGES = [
  { label: 'Ingested', icon: 'download', desc: 'Batch validated & inserted' },
  { label: 'Processed', icon: 'transform', desc: 'Diagnosis codes crosswalked' },
  { label: 'Suspects', icon: 'neurology', desc: '8-Signal scoring engine' },
  { label: 'Evidence', icon: 'file_present', desc: 'Atomic claim references linked' },
  { label: 'LLM Ready', icon: 'done_all', desc: 'Structured prompt stored' },
];

export function PipelineStages({ currentStatus = 'COMPLETED', suspectsCount = 0 }) {
  const isFailed = currentStatus === 'FAILED';

  return (
    <div className="bg-surface-container-lowest rounded-2xl p-6 shadow-sm border border-outline-variant/20 flex flex-col gap-6">
      <div className="flex justify-between items-center">
        <div>
          <span className="font-mono text-xs font-semibold text-primary uppercase tracking-wider">
            Pipeline Architecture
          </span>
          <h3 className="font-manrope text-lg font-bold text-on-surface">
            Automated Execution Stages
          </h3>
        </div>
        <div className="flex items-center gap-1.5 px-3 py-1 bg-primary/10 text-primary border border-primary/20 rounded-full font-mono text-xs font-semibold">
          <span className="w-2 h-2 rounded-full bg-primary animate-pulse" />
          <span>Status: {currentStatus}</span>
        </div>
      </div>

      <div className="relative flex justify-between items-start pt-2 px-2">
        {/* Connecting Progress Line */}
        <div className="absolute top-[28px] left-[8%] right-[8%] h-[3px] bg-surface-container-high -z-0">
          <div
            className={`h-full transition-all duration-700 ${
              isFailed ? 'bg-error' : 'bg-primary'
            }`}
            style={{ width: isFailed ? '40%' : '100%' }}
          />
        </div>

        {STAGES.map((stage, idx) => {
          return (
            <div key={stage.label} className="relative z-10 flex flex-col items-center text-center gap-2 max-w-[100px]">
              <div
                className={`w-12 h-12 rounded-full flex items-center justify-center shadow-sm font-bold text-on-primary transition-all ${
                  isFailed && idx >= 2 ? 'bg-surface-container-high text-outline' : 'bg-primary text-on-primary'
                }`}
              >
                <span className="material-symbols-outlined text-[22px]">{stage.icon}</span>
              </div>
              <span className="font-mono text-xs font-bold text-on-surface uppercase tracking-wider">
                {stage.label}
              </span>
              <span className="text-[11px] text-on-surface-variant leading-tight">
                {stage.desc}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
