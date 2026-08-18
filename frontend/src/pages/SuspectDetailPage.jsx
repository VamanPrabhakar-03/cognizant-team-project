import React, { useEffect, useState } from 'react';
import { suspectsApi, reviewsApi } from '../api/index';
import { PageHeader } from '../components/common/PageHeader';
import { Badge } from '../components/common/Badge';
import { ScoreDonut } from '../components/common/ScoreDonut';
import { ScoreBarGrid } from '../components/common/ScoreBarGrid';
import { ReviewDecisionModal } from '../components/suspects/ReviewDecisionModal';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { formatDate } from '../utils/formatters';

export function SuspectDetailPage({ suspectId, onBack, onNavigateMember }) {
  const [data, setData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  // Review modal state
  const [isReviewOpen, setIsReviewOpen] = useState(false);
  const [isSubmittingReview, setIsSubmittingReview] = useState(false);
  const [successToast, setSuccessToast] = useState(null);

  const loadSuspectDetail = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await suspectsApi.getById(suspectId);
      setData(res);
    } catch (err) {
      setError(err.message || 'Failed to load suspect details.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadSuspectDetail();
  }, [suspectId]);

  const handleReviewSubmit = async (reviewPayload) => {
    setIsSubmittingReview(true);
    try {
      await reviewsApi.createDecision(reviewPayload);
      setIsReviewOpen(false);
      setSuccessToast(`Review decision saved successfully: ${reviewPayload.decision}`);
      // Refresh detail
      loadSuspectDetail();
    } catch (err) {
      alert(`Could not save review decision: ${err.message}`);
    } finally {
      setIsSubmittingReview(false);
    }
  };

  if (isLoading) {
    return <LoadingSpinner message="Retrieving clinical evidence and score signals..." />;
  }

  if (error || !data) {
    return (
      <div className="flex flex-col gap-4 p-8">
        <button
          onClick={onBack}
          className="self-start px-3 py-1.5 bg-surface-container rounded-lg text-xs font-mono text-on-surface flex items-center gap-1"
        >
          <span className="material-symbols-outlined text-[16px]">arrow_back</span>
          <span>Back to Suspect Queue</span>
        </button>
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl text-rose-800 text-sm font-mono">
          {error || 'Suspect record not found.'}
        </div>
      </div>
    );
  }

  const suspect = data.suspect || {};
  const llmReview = data.llm_review || {};
  const llmPayload = llmReview.output_payload || {};
  const references = suspect.evidence_references || [];
  const reasonFlags = suspect.reason_flags || [];
  const isEmerging = (suspect.suspect_type || suspect.gap_type || '').toUpperCase() === 'EMERGING';
  const evidenceBreakdown = llmPayload.evidence_breakdown || [];
  const verificationChecklist = llmPayload.verification_checklist || [];

  return (
    <div className="flex flex-col gap-6">
      {/* Back Button */}
      <div className="flex items-center justify-between">
        <button
          onClick={onBack}
          className="px-3.5 py-1.5 bg-surface-container rounded-xl text-xs font-mono text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high transition-colors flex items-center gap-1.5"
        >
          <span className="material-symbols-outlined text-[16px]">arrow_back</span>
          <span>Back to Suspect Queue</span>
        </button>

        <div className="flex items-center gap-2">
          <Badge tone={isEmerging ? 'pink' : 'violet'}>
            {suspect.suspect_type || suspect.gap_type || 'EMERGING'} GAP
          </Badge>
          <Badge tone={suspect.status === 'REVIEWED' ? 'success' : 'warning'}>
            {suspect.status || 'PENDING_REVIEW'}
          </Badge>
        </div>
      </div>

      {/* Page Header */}
      <PageHeader
        eyebrow="Clinical Intelligence & Evidence Dossier"
        title={`HCC ${suspect.hcc_v28}: ${suspect.hcc_description || 'Documentation Opportunity'}`}
        description={`CMS-HCC V28 Opportunity for Beneficiary ${suspect.bene_id} · Scored by 8-Signal Clinical Inference Engine.`}
        actions={
          <div className="flex items-center gap-3">
            <button
              onClick={() => onNavigateMember && onNavigateMember(suspect.bene_id)}
              className="px-4 py-2 bg-surface-container text-on-surface font-manrope font-semibold text-xs rounded-xl hover:bg-surface-container-high transition-colors flex items-center gap-1.5"
            >
              <span className="material-symbols-outlined text-[18px]">person</span>
              <span>View Member Profile</span>
            </button>
            <button
              onClick={() => setIsReviewOpen(true)}
              className="px-4 py-2 bg-primary text-on-primary font-manrope font-bold text-xs rounded-xl shadow hover:bg-primary/90 transition-all flex items-center gap-1.5"
            >
              <span className="material-symbols-outlined text-[18px]">rate_review</span>
              <span>Submit Clinical Decision</span>
            </button>
          </div>
        }
      />

      {successToast && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-emerald-800 text-sm flex items-center justify-between font-mono">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined">check_circle</span>
            <span>{successToast}</span>
          </div>
          <button onClick={() => setSuccessToast(null)} className="text-xs">✕</button>
        </div>
      )}

      {/* Top Grid: Member Info & Circular Confidence Ring */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Member Summary Card */}
        <div className="bg-surface-container-lowest rounded-2xl p-6 shadow-sm border border-outline-variant/20 flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-3 mb-4">
              <div className="w-12 h-12 rounded-full bg-primary-container text-on-primary-container flex items-center justify-center font-manrope font-extrabold text-base shadow-sm">
                {String(suspect.bene_id).slice(-2)}
              </div>
              <div className="flex flex-col min-w-0">
                <h3 className="font-manrope text-base font-bold text-on-surface truncate">
                  Beneficiary {suspect.bene_id}
                </h3>
                <span className="font-mono text-xs text-on-surface-variant">
                  CMS Medicare Advantage
                </span>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 mt-4">
              <div className="p-3 bg-surface rounded-xl border border-outline-variant/15">
                <span className="font-mono text-[10px] text-on-surface-variant uppercase">First Evidence</span>
                <p className="font-mono text-xs font-bold text-on-surface mt-0.5">
                  {formatDate(suspect.first_evidence_date)}
                </p>
              </div>
              <div className="p-3 bg-surface rounded-xl border border-outline-variant/15">
                <span className="font-mono text-[10px] text-on-surface-variant uppercase">Last Evidence</span>
                <p className="font-mono text-xs font-bold text-on-surface mt-0.5">
                  {formatDate(suspect.last_evidence_date)}
                </p>
              </div>
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-outline-variant/15 flex items-center justify-between text-xs font-mono">
            <span className="text-on-surface-variant">Evidence Span:</span>
            <span className="font-bold text-primary">{suspect.evidence_span_days || 0} days</span>
          </div>
        </div>

        {/* Confidence Ring Dial */}
        <div className="bg-surface-container-lowest rounded-2xl p-6 shadow-sm border border-outline-variant/20 flex flex-col items-center justify-center">
          <span className="font-mono text-xs font-semibold text-on-surface-variant uppercase tracking-wider mb-2">
            ML Review Priority
          </span>
          <ScoreDonut score={suspect.ml_priority_score ?? suspect.priority_score ?? 0} size={150} />
          {suspect.ml_priority && (
            <span className="mt-2 font-mono text-xs font-bold text-primary">
              {suspect.ml_priority} {suspect.ml_review_rank ? `· Reviewer rank #${suspect.ml_review_rank}` : ''}
            </span>
          )}
        </div>

        {/* Rx Support & Context */}
        <div className="bg-surface-container-lowest rounded-2xl p-6 shadow-sm border border-outline-variant/20 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-3">
              <span className="font-mono text-xs font-semibold text-tertiary uppercase tracking-wider">
                Part D Rx Alignment
              </span>
              <span className="material-symbols-outlined text-tertiary text-[20px]">medication</span>
            </div>

            <h4 className="font-manrope text-base font-bold text-on-surface">
              {suspect.prescription_support_count || 0} Prescriptions Linked
            </h4>
            <p className="text-xs text-on-surface-variant mt-1 leading-relaxed">
              {(suspect.prescription_drug_codes || []).length > 0
                ? `National Drug Codes: ${(suspect.prescription_drug_codes || []).join(', ')}`
                : 'No explicit Part D prescription events matched for this HCC category.'}
            </p>
          </div>

          <div className="mt-4 p-3 bg-surface rounded-xl border border-outline-variant/15 text-xs text-on-surface leading-relaxed">
            <strong className="text-primary block font-mono text-[11px] uppercase mb-0.5">Clinical Summary:</strong>
            {suspect.evidence_summary || 'Evidence signals aggregated across outpatient and carrier claims.'}
          </div>
        </div>
      </div>

      {/* 8-Signal Score Dimensions Grid */}
      <div className="bg-surface-container-lowest rounded-2xl p-6 shadow-sm border border-outline-variant/20 flex flex-col gap-4">
        <div className="flex justify-between items-center">
          <div>
            <span className="font-mono text-xs font-semibold text-primary uppercase tracking-wider">
              Transparency & Explainability
            </span>
            <h3 className="font-manrope text-lg font-bold text-on-surface">
              8-Signal Feature Breakdown
            </h3>
          </div>
          <span className="font-mono text-xs text-on-surface-variant">Deterministic Model</span>
        </div>

        <ScoreBarGrid suspect={suspect} />
      </div>

      {/* AI-Assisted Clinical Review Explanation */}
      <div className="bg-gradient-to-r from-primary/5 via-surface to-tertiary/5 rounded-2xl p-6 shadow-sm border border-primary/20 flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-primary text-[24px]">neurology</span>
            <h3 className="font-manrope text-lg font-bold text-on-surface">
              AI Reviewer Explanation & Audit Rationale
            </h3>
          </div>
          <div className="flex items-center gap-2">
            <Badge tone="primary">
              {llmReview.model_name || 'Clinical-Inference-Synthesizer-v28'}
            </Badge>
            <Badge tone={llmReview.status === 'COMPLETED' ? 'success' : 'violet'}>
              {llmReview.status || 'LLM Review Ready'}
            </Badge>
          </div>
        </div>

        {/* Main Clinical Narrative */}
        <div className="p-4 bg-surface rounded-xl border border-outline-variant/20 text-sm text-on-surface leading-relaxed font-sans shadow-xs">
          <div className="flex items-center gap-1.5 text-xs font-mono font-bold text-primary mb-1 uppercase tracking-wide">
            <span className="material-symbols-outlined text-[16px]">summarize</span>
            <span>Clinical Documentation Summary</span>
          </div>
          <p className="mt-1">
            {llmReview.reviewer_summary ||
              suspect.evidence_summary ||
              `Clinical evidence shows persistent documentation for HCC ${suspect.hcc_v28}. Grounded in atomic service dates and validated against CMS-HCC V28 crosswalk rules.`}
          </p>
        </div>

        {/* Evidence Breakdown Points */}
        {evidenceBreakdown.length > 0 && (
          <div className="flex flex-col gap-1.5 bg-surface/50 p-3.5 rounded-xl border border-outline-variant/15">
            <span className="font-mono text-xs font-bold text-on-surface uppercase tracking-wide flex items-center gap-1.5">
              <span className="material-symbols-outlined text-tertiary text-[16px]">fact_check</span>
              <span>Evidence Analysis Breakdown</span>
            </span>
            <ul className="mt-1 flex flex-col gap-1 text-xs text-on-surface-variant list-none">
              {evidenceBreakdown.map((point, idx) => (
                <li key={idx} className="flex items-start gap-2">
                  <span className="text-primary font-bold">▪</span>
                  <span>{point}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Verification Checklist for Human Auditor */}
        {verificationChecklist.length > 0 && (
          <div className="flex flex-col gap-1.5 bg-surface/50 p-3.5 rounded-xl border border-outline-variant/15">
            <span className="font-mono text-xs font-bold text-primary uppercase tracking-wide flex items-center gap-1.5">
              <span className="material-symbols-outlined text-primary text-[16px]">checklist</span>
              <span>Human Auditor Verification Checklist</span>
            </span>
            <ul className="mt-1 flex flex-col gap-1.5 text-xs text-on-surface list-none">
              {verificationChecklist.map((item, idx) => (
                <li key={idx} className="flex items-start gap-2">
                  <span className="material-symbols-outlined text-emerald-600 text-[16px]">check_box</span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {reasonFlags.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-outline-variant/15">
            <span className="font-mono text-xs text-on-surface-variant font-semibold">Evidence Flags:</span>
            {reasonFlags.map((flag) => (
              <Badge key={flag} tone="pink">
                {flag}
              </Badge>
            ))}
          </div>
        )}
      </div>

      {/* Atomic Evidence References Table */}
      <div className="bg-surface-container-lowest rounded-2xl p-6 shadow-sm border border-outline-variant/20 flex flex-col gap-4">
        <div className="flex justify-between items-center">
          <div>
            <span className="font-mono text-xs font-semibold text-primary uppercase tracking-wider">
              Atomic Evidence
            </span>
            <h3 className="font-manrope text-lg font-bold text-on-surface">
              Supporting Claim & Encounter References
            </h3>
          </div>
          <Badge tone="slate">{references.length} Atomic Events</Badge>
        </div>

        {references.length === 0 ? (
          <div className="text-center py-6 text-on-surface-variant text-sm font-mono bg-surface rounded-xl border border-outline-variant/15">
            No atomic claim references recorded for this candidate.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-surface text-on-surface-variant border-b border-outline-variant/15 font-mono text-xs uppercase">
                  <th className="p-3 font-semibold">Date</th>
                  <th className="p-3 font-semibold">Source</th>
                  <th className="p-3 font-semibold">ICD-10 Code</th>
                  <th className="p-3 font-semibold">Claim ID</th>
                  <th className="p-3 font-semibold text-right">Designation</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-outline-variant/10 text-sm font-mono">
                {references.map((ref, idx) => (
                  <tr key={`${ref.claim_id || ref.event_id}-${idx}`} className="hover:bg-surface-container-low transition-colors">
                    <td className="p-3 font-bold text-on-surface">{formatDate(ref.date)}</td>
                    <td className="p-3">
                      <Badge tone="violet">{ref.source || 'CLAIM'}</Badge>
                    </td>
                    <td className="p-3 font-bold text-primary">{ref.diagnosis_code || '—'}</td>
                    <td className="p-3 text-on-surface-variant">{ref.claim_id || '—'}</td>
                    <td className="p-3 text-right">
                      {ref.is_principal ? (
                        <Badge tone="error" icon="star">
                          Principal Dx
                        </Badge>
                      ) : (
                        <span className="text-xs text-outline">Secondary Dx</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Review Decision Modal Dialog */}
      <ReviewDecisionModal
        suspect={suspect}
        isOpen={isReviewOpen}
        onClose={() => setIsReviewOpen(false)}
        onSubmit={handleReviewSubmit}
        isSubmitting={isSubmittingReview}
      />
    </div>
  );
}
