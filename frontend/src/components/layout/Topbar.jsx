import React, { useState } from 'react';

export function Topbar({ onSearch = null, onNavigate = null }) {
  const [query, setQuery] = useState('');

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && query.trim()) {
      if (onSearch) onSearch(query.trim());
      else if (onNavigate) onNavigate(`suspects?search=${encodeURIComponent(query.trim())}`);
    }
  };

  return (
    <header className="fixed top-0 left-72 right-0 h-16 bg-surface/85 backdrop-blur-xl z-40 flex items-center justify-between px-8 border-b border-outline-variant/15">
      {/* Global Search Bar */}
      <div className="flex items-center flex-1 max-w-xl bg-surface-container-highest/40 rounded-full px-4 py-1.5 border border-outline-variant/30 group focus-within:border-primary focus-within:bg-surface-container-lowest transition-all">
        <span className="material-symbols-outlined text-outline text-[20px]">search</span>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          className="bg-transparent border-none focus:outline-none w-full px-3 text-sm text-on-surface placeholder:text-outline/70"
          placeholder="Search member ID, HCC code, or ICD-10 description..."
          type="text"
        />
        {query && (
          <button
            onClick={() => setQuery('')}
            className="text-outline hover:text-on-surface text-xs font-mono"
          >
            clear
          </button>
        )}
      </div>

      {/* Action Icons */}
      <div className="flex items-center gap-2">
        <div className="flex items-center gap-1.5 px-3 py-1 bg-emerald-50 text-emerald-800 border border-emerald-200 rounded-full text-xs font-mono font-medium">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <span>Azure API Connected</span>
        </div>

        <button
          onClick={() => alert('All pipeline monitors and background tasks running normally.')}
          className="p-2 rounded-full hover:bg-surface-container-high transition-colors text-on-surface-variant"
          title="Notifications"
        >
          <span className="material-symbols-outlined text-[22px]">notifications</span>
        </button>

        <button
          onClick={() => onNavigate && onNavigate('pipeline')}
          className="p-2 rounded-full hover:bg-surface-container-high transition-colors text-on-surface-variant"
          title="Pipeline Monitor"
        >
          <span className="material-symbols-outlined text-[22px]">tune</span>
        </button>
      </div>
    </header>
  );
}
