import React, { useEffect, useState } from 'react';
import { reviewsApi } from '../api/index';
import { PageHeader } from '../components/common/PageHeader';
import { Badge } from '../components/common/Badge';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { EmptyState } from '../components/common/EmptyState';
import { formatDate, formatNumber } from '../utils/formatters';

export function ReviewsPage({ onSelectSuspect }) {
  const [reviews, setReviews] = useState([]);
  const [stats, setStats] = useState({ total: 0, decisions: {} });
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  // Filters
  const [decisionFilter, setDecisionFilter] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');

  const loadReviewsData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [reviewList, statRes] = await Promise.all([
        reviewsApi.list({ size: 100 }),
        reviewsApi.getStats().catch(() => ({ total_reviews: 0, decisions: {} })),
      ]);
      setReviews(reviewList.items || []);
      setStats(statRes);
    } catch (err) {
      setError(err.message || 'Failed to load review audit trail.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadReviewsData();
  }, []);

  const filteredReviews = reviews.filter((r) => {
    if (decisionFilter !== 'ALL' && r.decision !== decisionFilter) return false;
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      String(r.bene_id).toLowerCase().includes(q) ||
      String(r.hcc_v28).toLowerCase().includes(q) ||
      String(r.reviewer_id).toLowerCase().includes(q) ||
      (r.notes || '').toLowerCase().includes(q)
    );
  });

  const exportCsv = () => {
    if (filteredReviews.length === 0) return;
    const headers = ['Review ID', 'Bene ID', 'HCC Code', 'Decision', 'Reviewer', 'Timestamp', 'Notes'];
    const rows = filteredReviews.map((r) => [
      r.review_id,
      r.bene_id,
      r.hcc_v28,
      r.decision,
      r.reviewer_id,
      r.reviewed_at,
      `"${(r.notes || '').replace(/"/g, '""')}"`,
    ]);
    const csvContent = [headers.join(','), ...rows.map((row) => row.join(','))].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', `hcc_reviews_export_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="flex flex-col gap-6">
      {/* Page Header */}
      <PageHeader
        eyebrow="Compliance & Quality Assurance"
        title="Review Audit Trail"
        description="Comprehensive log of all HCC documentation review decisions, timestamps, and clinical notes for compliance and quality assurance."
        actions={
          <button
            onClick={exportCsv}
            disabled={filteredReviews.length === 0}
            className="px-4 py-2 bg-surface-container text-on-surface font-manrope font-semibold text-xs rounded-xl hover:bg-surface-container-high transition-colors flex items-center gap-1.5 disabled:opacity-40"
          >
            <span className="material-symbols-outlined text-[18px]">download</span>
            <span>Export Audit CSV</span>
          </button>
        }
      />

      {error && (
        <div className="p-4 bg-amber-50 border border-amber-200 rounded-xl text-amber-800 text-sm flex items-center gap-2 font-mono">
          <span className="material-symbols-outlined">warning</span>
          <span>{error}</span>
        </div>
      )}

      {/* Filter Section */}
      <div className="flex flex-wrap items-center justify-between gap-4 bg-surface-container-lowest p-4 rounded-2xl shadow-sm border border-outline-variant/20">
        <div className="flex items-center bg-surface-container-low rounded-xl px-3.5 py-2 flex-1 md:w-80 border border-outline-variant/20 focus-within:border-primary focus-within:bg-surface transition-all">
          <span className="material-symbols-outlined text-outline text-[18px] mr-2">search</span>
          <input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search member, HCC, reviewer, notes..."
            className="bg-transparent w-full focus:outline-none text-xs font-mono text-on-surface placeholder:text-outline"
          />
        </div>

        <div className="flex items-center gap-3">
          <select
            value={decisionFilter}
            onChange={(e) => setDecisionFilter(e.target.value)}
            className="bg-surface-container-low text-on-surface font-mono text-xs px-3 py-2 rounded-xl border border-outline-variant/20 outline-none"
          >
            <option value="ALL">All Decisions</option>
            <option value="SUPPORTED">Supported</option>
            <option value="NOT_SUPPORTED">Not Supported</option>
            <option value="INSUFFICIENT_EVIDENCE">Insufficient Evidence</option>
          </select>

          <button
            onClick={() => {
              setDecisionFilter('ALL');
              setSearchQuery('');
            }}
            className="px-3 py-2 bg-surface-container text-on-surface-variant font-mono text-xs rounded-xl hover:bg-surface-container-high"
          >
            Clear Filters
          </button>
        </div>
      </div>

      {/* Review Decisions Table */}
      {isLoading ? (
        <LoadingSpinner message="Loading audit trail records..." />
      ) : filteredReviews.length === 0 ? (
        <EmptyState
          title="No review records found"
          message="Completed review decisions will appear here as clinical reviewers triage suspects."
          icon="assignment_turned_in"
        />
      ) : (
        <div className="bg-surface-container-lowest rounded-2xl shadow-sm border border-outline-variant/20 overflow-hidden flex flex-col">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-surface-container-low text-on-surface-variant border-b border-outline-variant/20 font-mono text-xs uppercase">
                  <th className="p-4 font-semibold whitespace-nowrap">Review ID</th>
                  <th className="p-4 font-semibold whitespace-nowrap">Member ID</th>
                  <th className="p-4 font-semibold whitespace-nowrap">HCC Code</th>
                  <th className="p-4 font-semibold whitespace-nowrap">Decision</th>
                  <th className="p-4 font-semibold whitespace-nowrap">Reviewer</th>
                  <th className="p-4 font-semibold whitespace-nowrap">Timestamp</th>
                  <th className="p-4 font-semibold w-1/3">Clinical Notes Preview</th>
                  <th className="p-4 font-semibold text-right">View</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-outline-variant/15 text-sm">
                {filteredReviews.map((r) => {
                  const isSupported = r.decision === 'SUPPORTED';
                  const isNotSupported = r.decision === 'NOT_SUPPORTED';

                  return (
                    <tr
                      key={r.review_id}
                      onClick={() => onSelectSuspect && onSelectSuspect(r.suspect_id)}
                      className="hover:bg-surface-container-low/70 transition-colors group cursor-pointer"
                    >
                      <td className="p-4 font-mono text-xs text-on-surface-variant font-bold">
                        {r.review_id}
                      </td>
                      <td className="p-4 font-mono font-bold text-primary">
                        {r.bene_id}
                      </td>
                      <td className="p-4">
                        <span className="font-mono bg-primary/10 text-primary font-bold px-2 py-0.5 rounded text-xs">
                          HCC {r.hcc_v28}
                        </span>
                      </td>
                      <td className="p-4">
                        <Badge
                          tone={isSupported ? 'success' : isNotSupported ? 'error' : 'warning'}
                          icon={isSupported ? 'check_circle' : isNotSupported ? 'cancel' : 'help'}
                        >
                          {r.decision}
                        </Badge>
                      </td>
                      <td className="p-4 font-manrope text-xs font-semibold text-on-surface">
                        {r.reviewer_id || 'Dr. S. Chen'}
                      </td>
                      <td className="p-4 font-mono text-xs text-on-surface-variant whitespace-nowrap">
                        {formatDate(r.reviewed_at)}
                      </td>
                      <td className="p-4 text-xs text-on-surface-variant truncate max-w-xs">
                        {r.notes || 'Reviewed without extra notes.'}
                      </td>
                      <td className="p-4 text-right">
                        <button className="p-1 rounded-lg text-outline group-hover:text-primary transition-colors">
                          <span className="material-symbols-outlined text-[18px]">open_in_new</span>
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
