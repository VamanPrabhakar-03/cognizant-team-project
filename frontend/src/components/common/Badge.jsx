import React from 'react';

const TONES = {
  primary: 'bg-primary/10 text-primary border-primary/20',
  violet: 'bg-surface-container-high text-primary border-primary/20',
  pink: 'bg-tertiary-container/15 text-tertiary border-tertiary/20',
  success: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  warning: 'bg-amber-50 text-amber-800 border-amber-200',
  error: 'bg-error-container/60 text-error border-error/30',
  slate: 'bg-surface-container text-on-surface-variant border-outline-variant/30',
};

export function Badge({ children, tone = 'primary', className = '', icon = null }) {
  const toneStyle = TONES[tone] || TONES.primary;
  return (
    <span
      className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold font-mono tracking-wide border ${toneStyle} ${className}`}
    >
      {icon && <span className="material-symbols-outlined text-[14px]">{icon}</span>}
      {children}
    </span>
  );
}
