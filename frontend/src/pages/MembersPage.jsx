import React, { useEffect, useState } from 'react';
import { membersApi } from '../api/index';
import { PageHeader } from '../components/common/PageHeader';
import { MemberTable } from '../components/members/MemberTable';
import { MemberTimelineView } from '../components/members/MemberTimelineView';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { EmptyState } from '../components/common/EmptyState';
import { Badge } from '../components/common/Badge';
import { formatDate, formatNumber } from '../utils/formatters';

export function MembersPage({ initialMemberId = null, onSelectSuspect = null }) {
  const [data, setData] = useState({ items: [], total: 0, page: 1, size: 50 });
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState(initialMemberId || '');
  const [error, setError] = useState(null);

  // Selected Member Details
  const [selectedMemberId, setSelectedMemberId] = useState(initialMemberId);
  const [memberDetail, setMemberDetail] = useState(null);
  const [isDetailLoading, setIsDetailLoading] = useState(false);

  // Timeline
  const [timelineEvents, setTimelineEvents] = useState([]);
  const [selectedYear, setSelectedYear] = useState('');
  const [hccOnly, setHccOnly] = useState(false);
  const [isTimelineLoading, setIsTimelineLoading] = useState(false);

  const loadMembers = async (page = 1) => {
    setIsLoading(true);
    setError(null);
    try {
      const params = { page, size: 50 };
      if (searchQuery.trim()) params.search = searchQuery.trim();
      const res = await membersApi.list(params);
      setData(res);
    } catch (err) {
      setError(err.message || 'Failed to load members list.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadMembers(1);
  }, []);

  const loadMemberDetailAndTimeline = async (beneId) => {
    setSelectedMemberId(beneId);
    setIsDetailLoading(true);
    setIsTimelineLoading(true);

    try {
      const detailRes = await membersApi.getById(beneId);
      setMemberDetail(detailRes);
    } catch (err) {
      console.error('Failed to load member detail:', err);
    } finally {
      setIsDetailLoading(false);
    }

    try {
      const tlRes = await membersApi.getTimeline(beneId, {
        year: selectedYear,
        hcc_only: hccOnly,
        limit: 100,
      });
      setTimelineEvents(tlRes?.items || []);
    } catch (err) {
      console.error('Failed to load member timeline:', err);
    } finally {
      setIsTimelineLoading(false);
    }
  };

  useEffect(() => {
    if (initialMemberId) {
      loadMemberDetailAndTimeline(initialMemberId);
    }
  }, [initialMemberId]);

  useEffect(() => {
    if (selectedMemberId) {
      setIsTimelineLoading(true);
      membersApi
        .getTimeline(selectedMemberId, {
          year: selectedYear,
          hcc_only: hccOnly,
          limit: 100,
        })
        .then((tlRes) => setTimelineEvents(tlRes?.items || []))
        .finally(() => setIsTimelineLoading(false));
    }
  }, [selectedYear, hccOnly]);

  return (
    <div className="flex flex-col gap-6">
      {/* Page Header */}
      <PageHeader
        eyebrow="Beneficiary Registry"
        title="Member Longitudinal Profile"
        description="Comprehensive member demographics, documented 2021–2022 historical baseline HCCs, and 2023 evaluation timeline."
        actions={
          <button
            onClick={() => loadMembers(1)}
            className="px-4 py-2 bg-surface-container text-on-surface font-manrope font-semibold text-xs rounded-xl hover:bg-surface-container-high transition-colors flex items-center gap-1.5"
          >
            <span className="material-symbols-outlined text-[18px]">refresh</span>
            <span>Refresh Members</span>
          </button>
        }
      />

      {error && (
        <div className="p-4 bg-amber-50 border border-amber-200 rounded-xl text-amber-800 text-sm flex items-center gap-2 font-mono">
          <span className="material-symbols-outlined">warning</span>
          <span>{error}</span>
        </div>
      )}

      {/* Main Grid: Member List (Left) + Member Dossier & Timeline (Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Member List & Search */}
        <div className="lg:col-span-5 flex flex-col gap-4">
          <div className="flex items-center bg-surface-container-lowest rounded-2xl p-3.5 shadow-sm border border-outline-variant/20">
            <span className="material-symbols-outlined text-outline text-[18px] mr-2">search</span>
            <input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && loadMembers(1)}
              placeholder="Search beneficiary ID..."
              className="bg-transparent w-full focus:outline-none text-xs font-mono text-on-surface placeholder:text-outline"
            />
            <button
              onClick={() => loadMembers(1)}
              className="px-3 py-1 bg-primary text-on-primary font-manrope font-bold text-xs rounded-lg shadow"
            >
              Search
            </button>
          </div>

          {isLoading ? (
            <LoadingSpinner message="Loading beneficiary list..." />
          ) : (
            <div className="flex flex-col gap-2">
              <span className="font-mono text-xs text-on-surface-variant px-1">
                Showing {data.items?.length || 0} of {formatNumber(data.total)} members
              </span>
              <div className="bg-surface-container-lowest rounded-2xl border border-outline-variant/20 divide-y divide-outline-variant/15 overflow-hidden">
                {(data.items || []).map((m) => {
                  const isSelected = selectedMemberId === m.bene_id;
                  const genderText = m.sex === '1' ? 'M' : m.sex === '2' ? 'F' : '—';
                  return (
                    <div
                      key={m.bene_id}
                      onClick={() => loadMemberDetailAndTimeline(m.bene_id)}
                      className={`p-4 flex items-center justify-between cursor-pointer transition-all ${
                        isSelected
                          ? 'bg-primary/10 border-l-4 border-primary font-semibold'
                          : 'hover:bg-surface-container-low'
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <div
                          className={`w-9 h-9 rounded-full flex items-center justify-center font-mono text-xs font-bold ${
                            isSelected ? 'bg-primary text-on-primary' : 'bg-surface-container text-primary'
                          }`}
                        >
                          {String(m.bene_id).slice(-2)}
                        </div>
                        <div className="flex flex-col">
                          <span className="font-mono text-sm text-on-surface">{m.bene_id}</span>
                          <span className="text-xs text-on-surface-variant font-mono">
                            DOB: {formatDate(m.birth_date)} · {genderText} · {m.state || 'US'}
                          </span>
                        </div>
                      </div>
                      <span className="material-symbols-outlined text-outline text-[18px]">chevron_right</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* Right Column: Selected Member Detail & Chronological Timeline */}
        <div className="lg:col-span-7 flex flex-col gap-4">
          {!selectedMemberId ? (
            <EmptyState
              title="Select a Beneficiary"
              message="Click on any member in the list to view their longitudinal baseline and claim timeline."
              icon="person_search"
            />
          ) : isDetailLoading ? (
            <LoadingSpinner message={`Loading longitudinal profile for ${selectedMemberId}...`} />
          ) : (
            <div className="flex flex-col gap-6">
              {/* Member Profile Stats Card */}
              <div className="bg-surface-container-lowest rounded-2xl p-6 shadow-sm border border-outline-variant/20 flex flex-col gap-4">
                <div className="flex justify-between items-start">
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 rounded-full bg-primary text-on-primary flex items-center justify-center font-manrope font-extrabold text-base shadow-sm">
                      {String(selectedMemberId).slice(-2)}
                    </div>
                    <div>
                      <h3 className="font-manrope text-xl font-bold text-on-surface">
                        Member {selectedMemberId}
                      </h3>
                      <p className="font-mono text-xs text-on-surface-variant mt-0.5">
                        DOB: {formatDate(memberDetail?.member?.birth_date)} · State: {memberDetail?.member?.state || '—'} · Zip: {memberDetail?.member?.zip || '—'}
                      </p>
                    </div>
                  </div>
                  <Badge tone="primary">CMS Medicare</Badge>
                </div>

                {/* KPI Summary Grid */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2">
                  <div className="p-3 bg-surface rounded-xl border border-outline-variant/15 text-center">
                    <span className="font-mono text-[10px] text-on-surface-variant uppercase">Total Claims</span>
                    <p className="font-mono text-lg font-bold text-on-surface mt-0.5">
                      {memberDetail?.stats?.total_claims || 0}
                    </p>
                  </div>
                  <div className="p-3 bg-surface rounded-xl border border-outline-variant/15 text-center">
                    <span className="font-mono text-[10px] text-on-surface-variant uppercase">Total Diagnoses</span>
                    <p className="font-mono text-lg font-bold text-on-surface mt-0.5">
                      {memberDetail?.stats?.total_diagnoses || 0}
                    </p>
                  </div>
                  <div className="p-3 bg-surface rounded-xl border border-outline-variant/15 text-center">
                    <span className="font-mono text-[10px] text-on-surface-variant uppercase">Baseline HCCs</span>
                    <p className="font-mono text-lg font-bold text-primary mt-0.5">
                      {memberDetail?.stats?.baseline_hcc_count || (memberDetail?.baseline_hccs || []).length}
                    </p>
                  </div>
                  <div className="p-3 bg-surface rounded-xl border border-outline-variant/15 text-center">
                    <span className="font-mono text-[10px] text-on-surface-variant uppercase">Suspect Gaps</span>
                    <p className="font-mono text-lg font-bold text-tertiary mt-0.5">
                      {memberDetail?.stats?.suspect_hcc_count || (memberDetail?.suspects || []).length}
                    </p>
                  </div>
                </div>

                {/* Baseline HCCs Pills */}
                {(memberDetail?.baseline_hccs || []).length > 0 && (
                  <div className="flex flex-col gap-2 pt-2 border-t border-outline-variant/15">
                    <span className="font-mono text-xs font-semibold text-on-surface-variant uppercase">
                      2021–2022 Documented Baseline HCCs:
                    </span>
                    <div className="flex flex-wrap gap-2">
                      {(memberDetail?.baseline_hccs || []).map((b) => (
                        <span
                          key={b.hcc_v28}
                          className="px-2.5 py-1 rounded-lg bg-surface font-mono text-xs font-semibold text-primary border border-outline-variant/20"
                        >
                          HCC {b.hcc_v28} ({b.baseline_years || '2021|2022'})
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Longitudinal Medical Timeline */}
              <div className="bg-surface-container-lowest rounded-2xl p-6 shadow-sm border border-outline-variant/20 flex flex-col gap-4">
                <div className="flex justify-between items-center">
                  <div>
                    <span className="font-mono text-xs font-semibold text-primary uppercase tracking-wider">
                      Longitudinal Record
                    </span>
                    <h3 className="font-manrope text-lg font-bold text-on-surface">
                      Medical & Pharmacy Event Stream
                    </h3>
                  </div>
                  <Badge tone="slate">{timelineEvents.length} Events</Badge>
                </div>

                {isTimelineLoading ? (
                  <LoadingSpinner message="Filtering event stream..." />
                ) : (
                  <MemberTimelineView
                    events={timelineEvents}
                    selectedYear={selectedYear}
                    onSelectYear={setSelectedYear}
                    hccOnly={hccOnly}
                    onToggleHccOnly={setHccOnly}
                  />
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
