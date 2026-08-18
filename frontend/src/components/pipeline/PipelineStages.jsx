import React, { useEffect, useState } from 'react';

const STAGES = [
  { id: 1, label: 'Unpack & Cleanse', icon: 'inventory_2', desc: 'Explode wide ICD columns & normalize dates' },
  { id: 2, label: 'V28 Crosswalk', icon: 'schema', desc: 'ICD-10 to CMS-HCC mapping & timeline link' },
  { id: 3, label: 'Gap Detection', icon: 'difference', desc: 'Compare vs 2-year historical member baseline' },
  { id: 4, label: 'ML Prioritization', icon: 'model_training', desc: '8-signal feature scoring & SVM inference' },
  { id: 5, label: 'LLM Synthesis', icon: 'neurology', desc: 'AI clinical rationale & audit checklist' },
  { id: 6, label: 'Queue Ready', icon: 'checklist', desc: 'Rank-ordered in human reviewer workspace' },
];

export function PipelineStages({ isUploading = false, currentStatus = 'IDLE', result = null }) {
  const [activeStage, setActiveStage] = useState(1);

  useEffect(() => {
    let interval = null;
    if (isUploading) {
      setActiveStage(1);
      interval = setInterval(() => {
        setActiveStage((prev) => (prev < 5 ? prev + 1 : 5));
      }, 1200);
    } else if (result) {
      setActiveStage(6);
    } else {
      setActiveStage(0);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [isUploading, result]);

  const isFailed = currentStatus === 'FAILED';

  return (
    <div className="bg-surface-container-lowest rounded-2xl p-6 shadow-sm border border-outline-variant/20 flex flex-col gap-6">
      <div className="flex justify-between items-center">
        <div>
          <span className="font-mono text-xs font-semibold text-primary uppercase tracking-wider">
            Pipeline Architecture
          </span>
          <h3 className="font-manrope text-lg font-bold text-on-surface">
            Automated Execution Lifecycle
          </h3>
        </div>
        <div className="flex items-center gap-1.5 px-3 py-1 bg-surface border border-outline-variant/20 rounded-full font-mono text-xs font-semibold">
          {isUploading ? (
            <>
              <span className="w-2 h-2 rounded-full bg-amber-500 animate-ping" />
              <span className="text-amber-700">Stage {activeStage} of 6: Processing</span>
            </>
          ) : result ? (
            <>
              <span className="w-2 h-2 rounded-full bg-emerald-500" />
              <span className="text-emerald-700">Completed · {result.suspects || 0} Suspects Generated</span>
            </>
          ) : (
            <>
              <span className="w-2 h-2 rounded-full bg-outline/50" />
              <span className="text-on-surface-variant">Awaiting Ingestion</span>
            </>
          )}
        </div>
      </div>

      {/* Progressive Step View */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {STAGES.map((stage) => {
          const isDone = activeStage > stage.id || (!isUploading && result && !isFailed);
          const isCurrent = isUploading && activeStage === stage.id;
          const isPending = activeStage < stage.id && !result;

          return (
            <div
              key={stage.id}
              className={`p-3 rounded-xl border flex flex-col items-center text-center transition-all ${
                isCurrent
                  ? 'bg-primary/10 border-primary shadow-xs scale-[1.02]'
                  : isDone
                    ? 'bg-emerald-50/60 border-emerald-200 text-emerald-900'
                    : 'bg-surface-container-low border-outline-variant/15 opacity-60'
              }`}
            >
              <div
                className={`w-10 h-10 rounded-full flex items-center justify-center mb-2 font-bold transition-all ${
                  isCurrent
                    ? 'bg-primary text-on-primary animate-bounce'
                    : isDone
                      ? 'bg-emerald-600 text-white'
                      : 'bg-surface-container-high text-outline'
                }`}
              >
                <span className="material-symbols-outlined text-[20px]">
                  {isDone ? 'check' : stage.icon}
                </span>
              </div>
              <span className="font-mono text-[11px] font-bold text-on-surface uppercase tracking-wide">
                {stage.label}
              </span>
              <span className="text-[10px] text-on-surface-variant leading-tight mt-1">
                {stage.desc}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
