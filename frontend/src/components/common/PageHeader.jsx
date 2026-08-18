import React from 'react';

export function LoadingSpinner({ message = 'Loading clinical intelligence…', className = '' }) {
  return (
    <div className={`flex flex-col items-center justify-center p-12 text-center text-on-surface-variant ${className}`}>
      <div className="w-10 h-10 border-4 border-primary/20 border-t-primary rounded-full animate-spin mb-4" />
      <p className="font-manrope text-sm font-semibold tracking-wide">{message}</p>
    </div>
  );
}

export function EmptyState({
  title = 'No records found',
  message = 'No data matching the selected criteria is available.',
  icon = 'inbox',
  action = null,
  className = '',
}) {
  return (
    <div className={`flex flex-col items-center justify-center p-12 text-center bg-surface-container-lowest rounded-2xl border border-outline-variant/20 shadow-sm ${className}`}>
      <div className="w-14 h-14 rounded-full bg-surface-container flex items-center justify-center text-outline mb-4">
        <span className="material-symbols-outlined text-[28px]">{icon}</span>
      </div>
      <h3 className="font-manrope text-lg font-bold text-on-surface mb-1">{title}</h3>
      <p className="text-sm text-on-surface-variant max-w-md mb-4">{message}</p>
      {action}
    </div>
  );
}

export function PageHeader({
  eyebrow = null,
  title,
  description = null,
  actions = null,
  className = '',
}) {
  return (
    <div className={`flex flex-col md:flex-row md:items-end justify-between gap-4 pb-6 ${className}`}>
      <div className="flex flex-col gap-1 max-w-2xl">
        {eyebrow && (
          <span className="font-mono text-xs font-semibold text-primary uppercase tracking-wider">
            {eyebrow}
          </span>
        )}
        <h1 className="font-manrope text-2xl md:text-3xl font-bold text-on-surface tracking-tight">
          {title}
        </h1>
        {description && (
          <p className="text-sm text-on-surface-variant leading-relaxed">
            {description}
          </p>
        )}
      </div>
      {actions && <div className="flex items-center gap-3 flex-shrink-0">{actions}</div>}
    </div>
  );
}
