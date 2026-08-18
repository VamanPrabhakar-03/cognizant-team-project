import React from 'react';
import { formatScore, getPriorityTier } from '../../utils/formatters';

export function ScoreDonut({ score = 0, size = 180, className = '' }) {
  const percent = formatScore(score);
  const tier = getPriorityTier(score);

  // Circumference for r=42 is 2 * PI * 42 ≈ 263.9
  const radius = 42;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (percent / 100) * circumference;

  const gradientId = `score-grad-${Math.round(score * 1000)}`;

  let tierColor = 'text-primary';
  let tierBadge = 'bg-primary/10 text-primary';
  if (tier === 'HIGH') {
    tierColor = 'text-error';
    tierBadge = 'bg-error-container/60 text-error';
  } else if (tier === 'MEDIUM') {
    tierColor = 'text-secondary';
    tierBadge = 'bg-secondary-container/30 text-secondary';
  }

  return (
    <div className={`flex flex-col items-center justify-center text-center ${className}`}>
      <div className="relative flex items-center justify-center group" style={{ width: size, height: size }}>
        {/* Outer track */}
        <svg className="absolute inset-0 w-full h-full -rotate-90" viewBox="0 0 100 100">
          <circle
            className="text-surface-dim stroke-current"
            cx="50"
            cy="50"
            fill="none"
            r={radius}
            strokeWidth="8"
          />
        </svg>

        {/* Animated Progress Ring */}
        <svg className="absolute inset-0 w-full h-full -rotate-90" viewBox="0 0 100 100">
          <defs>
            <linearGradient id={gradientId} x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#5300b7" />
              <stop offset="100%" stopColor={tier === 'HIGH' ? '#ba1a1a' : '#81004c'} />
            </linearGradient>
          </defs>
          <circle
            cx="50"
            cy="50"
            fill="none"
            r={radius}
            stroke={`url(#${gradientId})`}
            strokeWidth="8"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            className="transition-all duration-1000 ease-out"
          />
        </svg>

        {/* Center Content */}
        <div className="flex flex-col items-center justify-center relative z-10 transition-transform duration-300 group-hover:scale-105">
          <span className={`font-manrope text-4xl font-extrabold tracking-tight ${tierColor}`}>
            {percent}
          </span>
          <span className="font-mono text-[11px] font-semibold uppercase tracking-wider text-on-surface-variant mt-0.5">
            {tier} Priority
          </span>
        </div>
      </div>

      <div className={`inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-semibold font-mono mt-2 border ${tierBadge}`}>
        <span className="material-symbols-outlined text-[14px]">
          {tier === 'HIGH' ? 'priority_high' : tier === 'MEDIUM' ? 'tune' : 'info'}
        </span>
        <span>{tier === 'HIGH' ? 'Action Required' : `${tier} Confidence`}</span>
      </div>
    </div>
  );
}
