import React from 'react';
import { formatDate } from '../../utils/formatters';

export function MemberTable({ items = [], onSelectMember }) {
  return (
    <div className="bg-surface-container-lowest rounded-2xl shadow-sm border border-outline-variant/20 overflow-hidden flex flex-col">
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-surface-container-low text-on-surface-variant border-b border-outline-variant/20 font-mono text-xs uppercase tracking-wider">
              <th className="p-4 font-semibold whitespace-nowrap">Beneficiary ID</th>
              <th className="p-4 font-semibold whitespace-nowrap">Date of Birth</th>
              <th className="p-4 font-semibold whitespace-nowrap">Gender</th>
              <th className="p-4 font-semibold whitespace-nowrap">State</th>
              <th className="p-4 font-semibold whitespace-nowrap">Zip Code</th>
              <th className="p-4 font-semibold whitespace-nowrap">Enrollment Years</th>
              <th className="p-4 font-semibold whitespace-nowrap text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-outline-variant/15 text-sm">
            {items.map((m) => {
              const genderText = m.sex === '1' ? 'Male' : m.sex === '2' ? 'Female' : (m.sex || '—');
              return (
                <tr
                  key={m.bene_id}
                  onClick={() => onSelectMember(m.bene_id)}
                  className="hover:bg-surface-container-low/70 transition-colors group cursor-pointer"
                >
                  <td className="p-4 font-mono font-bold text-primary group-hover:underline flex items-center gap-2">
                    <div className="w-7 h-7 rounded-full bg-primary/10 text-primary flex items-center justify-center font-mono text-xs font-bold">
                      {String(m.bene_id).slice(-2)}
                    </div>
                    <span>{m.bene_id}</span>
                  </td>
                  <td className="p-4 font-mono text-xs text-on-surface">
                    {formatDate(m.birth_date)}
                  </td>
                  <td className="p-4 text-on-surface">
                    {genderText}
                  </td>
                  <td className="p-4">
                    <span className="font-mono bg-surface-container px-2 py-0.5 rounded text-xs">
                      {m.state || '—'}
                    </span>
                  </td>
                  <td className="p-4 font-mono text-xs text-on-surface-variant">
                    {m.zip || '—'}
                  </td>
                  <td className="p-4">
                    <span className="font-mono text-xs text-primary font-semibold">
                      {m.enrollment_years || '2023|2024|2025'}
                    </span>
                  </td>
                  <td className="p-4 text-right">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectMember(m.bene_id);
                      }}
                      className="p-1.5 rounded-lg text-outline hover:text-primary hover:bg-surface-container transition-all group-hover:translate-x-1"
                    >
                      <span className="material-symbols-outlined text-[20px]">chevron_right</span>
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
