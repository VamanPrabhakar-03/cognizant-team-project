import React from 'react';

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
export default EmptyState;
