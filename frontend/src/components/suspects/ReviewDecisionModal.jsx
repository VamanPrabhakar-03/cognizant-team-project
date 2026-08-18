import React, { useState } from 'react';
import { REVIEW_DECISIONS } from '../../utils/constants';

export function ReviewDecisionModal({
  suspect,
  isOpen,
  onClose,
  onSubmit,
  isSubmitting = false,
}) {
  const [decision, setDecision] = useState('SUPPORTED');
  const [notes, setNotes] = useState('');

  if (!isOpen || !suspect) return null;

  const handleSubmit = (e) => {
    e.preventDefault();
    onSubmit({
      suspect_id: suspect.suspect_id,
      bene_id: suspect.bene_id,
      hcc_v28: String(suspect.hcc_v28),
      suspect_type: suspect.suspect_type || suspect.gap_type || 'EMERGING',
      priority_score: suspect.priority_score || 0.0,
      decision,
      notes: notes.trim() || 'Reviewed in Clinical Assistant',
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-on-surface/40 backdrop-blur-xs animate-fadeIn">
      <div className="bg-surface-container-lowest rounded-2xl max-w-lg w-full p-6 shadow-xl border border-outline-variant/30 relative flex flex-col gap-5">
        {/* Header */}
        <div className="flex justify-between items-start border-b border-outline-variant/15 pb-4">
          <div>
            <span className="font-mono text-xs font-semibold text-primary uppercase tracking-wider">
              Clinical Review Decision
            </span>
            <h2 className="font-manrope text-xl font-bold text-on-surface">
              HCC {suspect.hcc_v28}: {suspect.hcc_description || 'Documentation Opportunity'}
            </h2>
            <p className="text-xs text-on-surface-variant mt-0.5">
              Member ID: <span className="font-mono font-bold text-on-surface">{suspect.bene_id}</span> · Score:{' '}
              <span className="font-mono font-bold">{Math.round((suspect.priority_score || 0) * 100)}%</span>
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-outline hover:text-on-surface hover:bg-surface-container transition-colors"
          >
            <span className="material-symbols-outlined text-[20px]">close</span>
          </button>
        </div>

        {/* Decision Options */}
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <label className="font-mono text-xs font-semibold text-on-surface uppercase tracking-wider">
              Select Decision
            </label>
            <div className="grid grid-cols-1 gap-2.5">
              {Object.entries(REVIEW_DECISIONS).map(([key, config]) => {
                const isSelected = decision === key;
                return (
                  <label
                    key={key}
                    onClick={() => setDecision(key)}
                    className={`flex items-start gap-3 p-3.5 rounded-xl border cursor-pointer transition-all ${
                      isSelected
                        ? 'bg-primary/5 border-primary shadow-xs ring-1 ring-primary'
                        : 'bg-surface border-outline-variant/30 hover:bg-surface-container-low'
                    }`}
                  >
                    <input
                      type="radio"
                      name="decision"
                      value={key}
                      checked={isSelected}
                      onChange={() => setDecision(key)}
                      className="mt-0.5 text-primary focus:ring-primary"
                    />
                    <div className="flex flex-col flex-1">
                      <div className="flex items-center gap-1.5">
                        <span className="material-symbols-outlined text-[18px] text-primary">{config.icon}</span>
                        <span className="font-manrope font-bold text-sm text-on-surface">{config.label}</span>
                      </div>
                      <span className="text-xs text-on-surface-variant mt-0.5">{config.description}</span>
                    </div>
                  </label>
                );
              })}
            </div>
          </div>

          {/* Reviewer Notes */}
          <div className="flex flex-col gap-1.5">
            <label className="font-mono text-xs font-semibold text-on-surface uppercase tracking-wider">
              Clinical Reviewer Notes
            </label>
            <textarea
              rows={3}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Add audit rationale, medical record page reference, or physician query notes..."
              className="w-full bg-surface-container-lowest border border-outline-variant/30 rounded-xl p-3 text-sm text-on-surface placeholder:text-outline focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary"
            />
          </div>

          {/* Action Buttons */}
          <div className="flex justify-end gap-3 pt-2 border-t border-outline-variant/15">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm font-manrope font-semibold text-on-surface-variant hover:bg-surface-container rounded-xl transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-5 py-2 text-sm font-manrope font-bold text-on-primary bg-primary rounded-xl shadow hover:bg-primary/90 transition-all flex items-center gap-1.5 disabled:opacity-50"
            >
              {isSubmitting ? (
                <>
                  <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span>Saving...</span>
                </>
              ) : (
                <>
                  <span className="material-symbols-outlined text-[18px]">check</span>
                  <span>Confirm Decision</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
