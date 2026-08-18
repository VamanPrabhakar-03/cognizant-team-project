import React from 'react';

export function LoadingSpinner({ message = 'Loading clinical intelligence…', className = '' }) {
  return (
    <div className={`flex flex-col items-center justify-center p-12 text-center text-on-surface-variant ${className}`}>
      <div className="w-10 h-10 border-4 border-primary/20 border-t-primary rounded-full animate-spin mb-4" />
      <p className="font-manrope text-sm font-semibold tracking-wide text-on-surface">{message}</p>
    </div>
  );
}
export default LoadingSpinner;
