import React from 'react';
import { formatNumber } from '../../utils/formatters';

export function MetricCard({
  label,
  value,
  helper,
  icon,
  trend = null,
  tone = 'primary',
  className = '',
}) {
  const isTertiary = tone === 'tertiary' || tone === 'pink';
  const topBarColor = isTertiary ? 'bg-tertiary' : 'bg-primary';
  const iconColor = isTertiary ? 'text-tertiary' : 'text-primary';
  const iconBg = isTertiary ? 'bg-tertiary-container/15' : 'bg-primary/10';

  return (
    <div
      className={`bg-surface-container-lowest rounded-2xl p-6 shadow-sm border border-outline-variant/20 relative overflow-hidden flex flex-col justify-between hover:shadow-md transition-shadow ${className}`}
    >
      <div className={`absolute top-0 left-0 w-full h-[2px] ${topBarColor}`} />

      <div className="flex justify-between items-start mb-3">
        <span className="font-mono text-xs font-semibold text-on-surface-variant uppercase tracking-wider">
          {label}
        </span>
        {icon && (
          <span className={`material-symbols-outlined ${iconColor} ${iconBg} p-1.5 rounded-full text-[20px]`}>
            {icon}
          </span>
        )}
      </div>

      <div className="flex items-baseline gap-2">
        <span className="font-manrope text-3xl md:text-4xl font-extrabold text-on-surface">
          {typeof value === 'number' ? formatNumber(value) : value}
        </span>
        {trend && (
          <span className={`text-xs font-semibold ${trend.startsWith('+') ? 'text-primary' : 'text-outline'}`}>
            {trend}
          </span>
        )}
      </div>

      {helper && (
        <div className="mt-3 flex items-center justify-between text-xs text-on-surface-variant font-medium">
          <span>{helper}</span>
        </div>
      )}

      {/* Mini Sparkline Graphic */}
      <div className="mt-3 h-5 w-full">
        <svg
          className={`w-full h-full ${isTertiary ? 'text-tertiary' : 'text-primary'} opacity-20`}
          preserveAspectRatio="none"
          viewBox="0 0 100 20"
        >
          <path
            d="M0,15 Q10,5 20,10 T40,5 T60,15 T80,5 T100,10"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            vectorEffect="non-scaling-stroke"
          />
        </svg>
      </div>
    </div>
  );
}
