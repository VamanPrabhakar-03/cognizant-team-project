import React from 'react';
import { NAV_ITEMS } from '../../utils/constants';

export function Sidebar({ currentRoute, onNavigate }) {
  return (
    <aside className="fixed left-0 top-0 h-full w-72 bg-surface-container-low z-50 flex flex-col border-r border-outline-variant/30 select-none">
      {/* Brand Header */}
      <div className="h-16 flex items-center px-6 gap-3 border-b border-outline-variant/10">
        <div className="w-9 h-9 rounded-xl bg-primary flex items-center justify-center text-on-primary shadow-sm">
          <span className="material-symbols-outlined text-[22px]">health_and_safety</span>
        </div>
        <div className="flex flex-col">
          <span className="font-manrope text-lg font-extrabold text-primary tracking-tight leading-none">
            HCC Assistant
          </span>
          <span className="font-mono text-[10px] text-on-surface-variant uppercase tracking-widest mt-0.5">
            Risk Review AI
          </span>
        </div>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 px-4 mt-6 flex flex-col gap-1.5 overflow-y-auto">
        {NAV_ITEMS.map((item) => {
          const isActive =
            currentRoute === item.id ||
            (item.id === 'suspects' && currentRoute.startsWith('suspect/')) ||
            (item.id === 'members' && currentRoute.startsWith('member/'));

          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              className={`flex items-center px-4 py-3 rounded-xl transition-all duration-200 text-left group ${
                isActive
                  ? 'bg-primary-container text-on-primary-container shadow-sm font-semibold'
                  : 'text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface'
              }`}
            >
              <span
                className={`material-symbols-outlined mr-3 transition-colors ${
                  isActive ? 'text-on-primary-container' : 'text-outline group-hover:text-primary'
                }`}
              >
                {item.icon}
              </span>
              <span className="font-manrope text-sm">{item.label}</span>
            </button>
          );
        })}
      </nav>

      {/* Profile Card / User Badge */}
      <div className="p-4 border-t border-outline-variant/20">
        <div className="flex items-center gap-3 p-3 bg-surface rounded-xl border border-outline-variant/20 shadow-sm">
          <div className="w-10 h-10 rounded-full bg-primary-container text-on-primary-container flex items-center justify-center font-manrope font-bold text-sm shadow-sm">
            SC
          </div>
          <div className="overflow-hidden flex-1">
            <p className="font-manrope text-xs font-bold text-on-surface truncate">Dr. Sarah Chen</p>
            <p className="font-mono text-[10px] text-on-surface-variant truncate">Clinical Reviewer</p>
          </div>
          <span className="w-2 h-2 rounded-full bg-emerald-500" title="Active Session" />
        </div>
      </div>
    </aside>
  );
}
