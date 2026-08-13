"""
Interactive Console Application & Review Station for UC03 - HCC Suspecting Engine

Allows clinical coders and auditors to:
  1. View high-level pipeline stats and suspect distributions
  2. Browse and filter candidate HCC review opportunities (Emerging & Recapture)
  3. Inspect member profiles, historical baseline, and complete medical timelines
  4. Perform interactive human review with audit trail logging (SUPPORT / REJECT / INSUFFICIENT_EVIDENCE)
  5. Search diagnosis and prescription events safely without crashing memory

Run with:
    python src/review_console.py
"""

import csv
import os
import sys
from datetime import datetime
from pathlib import Path
from collections import Counter

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR     = PROJECT_ROOT / "data"

MEMBERS_CSV       = DATA_DIR / "members.csv"
BASELINE_CSV      = DATA_DIR / "member_hcc_baseline.csv"
SUSPECTS_CSV      = DATA_DIR / "suspects.csv"
TIMELINE_CSV      = DATA_DIR / "member_timeline.csv"
HCC_MAPPING_CSV   = DATA_DIR / "hcc_mapping.csv"
DECISIONS_CSV     = DATA_DIR / "review_decisions.csv"


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def print_header(title: str):
    print("\n" + "=" * 78)
    print(f"  {title}")
    print("=" * 78)


def load_members():
    members = {}
    if MEMBERS_CSV.exists():
        with open(MEMBERS_CSV, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                members[r["bene_id"]] = r
    return members


def load_suspects():
    suspects = []
    if SUSPECTS_CSV.exists():
        with open(SUSPECTS_CSV, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                suspects.append(r)
    return suspects


def load_baseline():
    baseline = {}
    if BASELINE_CSV.exists():
        with open(BASELINE_CSV, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                bid = r["bene_id"]
                if bid not in baseline:
                    baseline[bid] = []
                baseline[bid].append(r)
    return baseline


def load_decisions():
    decisions = {}
    if DECISIONS_CSV.exists():
        with open(DECISIONS_CSV, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                decisions[r["suspect_id"]] = r
    return decisions


def save_decision(suspect, decision, notes=""):
    fieldnames = [
        "suspect_id", "bene_id", "hcc_v28", "suspect_type", "priority_score",
        "decision", "notes", "reviewer_timestamp"
    ]
    file_exists = DECISIONS_CSV.exists()
    with open(DECISIONS_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            "suspect_id": suspect["suspect_id"],
            "bene_id": suspect["bene_id"],
            "hcc_v28": suspect["hcc_v28"],
            "suspect_type": suspect["suspect_type"],
            "priority_score": suspect["priority_score"],
            "decision": decision,
            "notes": notes,
            "reviewer_timestamp": datetime.now().isoformat(timespec="seconds"),
        })


def get_member_timeline(bene_id: str, limit: int = 100):
    """Safely stream timeline for a single member without loading 2GB in memory."""
    events = []
    if not TIMELINE_CSV.exists():
        return events

    with open(TIMELINE_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["bene_id"] == bene_id:
                events.append(row)
    # Sort chronologically
    events.sort(key=lambda x: (x["event_date"], x["event_type"]))
    return events


# ── View 1: Overview & Pipeline Metrics ────────────────────────────────────────

def show_overview(members, suspects, baseline, decisions):
    print_header("PIPELINE OVERVIEW & METRICS")

    emerging = [s for s in suspects if s["suspect_type"] == "EMERGING"]
    recapture = [s for s in suspects if s["suspect_type"] == "RECAPTURE"]

    high_prio = [s for s in suspects if float(s["priority_score"]) >= 0.75]
    med_prio  = [s for s in suspects if 0.50 <= float(s["priority_score"]) < 0.75]
    low_prio  = [s for s in suspects if float(s["priority_score"]) < 0.50]

    reviewed_count = len(decisions)
    pending_count  = len(suspects) - reviewed_count

    print(f"\n  [ Population & Cohort ]")
    print(f"    Total Registered Members        : {len(members):,}")
    print(f"    Members with Baseline Documented: {len(baseline):,}")
    print(f"    Total Documented Baseline HCCs  : {sum(len(v) for v in baseline.values()):,}")

    print(f"\n  [ Suspecting Review Opportunities ]")
    print(f"    Total Candidates Identified     : {len(suspects):,}")
    print(f"    - Type A: Emerging HCCs (2023)  : {len(emerging):,}")
    print(f"    - Type B: Recapture Opportunities: {len(recapture):,}")

    print(f"\n  [ Priority Scoring Tiers ]")
    print(f"    High Priority   (Score >= 0.75) : {len(high_prio):,} ({len(high_prio)/len(suspects)*100:.1f}%)")
    print(f"    Medium Priority (0.50 <= S < 0.75): {len(med_prio):,} ({len(med_prio)/len(suspects)*100:.1f}%)")
    print(f"    Low Priority    (Score < 0.50)  : {len(low_prio):,} ({len(low_prio)/len(suspects)*100:.1f}%)")

    print(f"\n  [ Human Review & Audit Status ]")
    print(f"    Reviewed Decisions Recorded     : {reviewed_count:,}")
    print(f"    Pending Clinical Review         : {pending_count:,}")

    if reviewed_count > 0:
        dec_counts = Counter(d["decision"] for d in decisions.values())
        print(f"      - SUPPORTED           : {dec_counts.get('SUPPORTED', 0):,}")
        print(f"      - NOT_SUPPORTED       : {dec_counts.get('NOT_SUPPORTED', 0):,}")
        print(f"      - INSUFFICIENT_EVID   : {dec_counts.get('INSUFFICIENT_EVIDENCE', 0):,}")

    input("\nPress [Enter] to return to the main menu...")


# ── View 2: Search Member Profile & Timeline ───────────────────────────────────

def show_member_search(members, suspects, baseline):
    print_header("MEMBER SEARCH & TIMELINE INSPECTION")
    print("Tip: Enter a Member ID (e.g. -10000010254968) or press [Enter] to see sample members with opportunities.")

    query = input("\nEnter BENE_ID: ").strip()

    if not query:
        # Show sample members with emerging/recapture suspects
        sample_bids = []
        for s in suspects[:15]:
            if s["bene_id"] not in sample_bids:
                sample_bids.append(s["bene_id"])

        print("\nSample Members with Opportunities:")
        for idx, bid in enumerate(sample_bids[:10], 1):
            m = members.get(bid, {})
            num_susp = sum(1 for s in suspects if s["bene_id"] == bid)
            print(f"  [{idx}] {bid} (Sex: {m.get('sex','?')}, State: {m.get('state','?')}, Suspects: {num_susp})")

        choice = input("\nSelect number (1-10) or enter custom ID: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(sample_bids):
            query = sample_bids[int(choice) - 1]
        elif choice:
            query = choice
        else:
            return

    if query not in members:
        print(f"\n[!] Member ID '{query}' not found in registry.")
        input("\nPress [Enter] to return...")
        return

    m = members[query]
    m_baseline = baseline.get(query, [])
    m_suspects = [s for s in suspects if s["bene_id"] == query]

    print("\n" + "-" * 78)
    print(f"  MEMBER PROFILE: {query}")
    print("-" * 78)
    print(f"  Birth Date : {m.get('birth_date','')} | Sex: {m.get('sex','')} | Race: {m.get('race','')}")
    print(f"  Location   : State {m.get('state','')}, County {m.get('county','')}, Zip {m.get('zip','')}")
    print(f"  Enrollment : {m.get('enrollment_years','')} | ESRD: {m.get('esrd_indicator','')}")

    print(f"\n  [ Historical Documented Baseline (2021-2022) ] ({len(m_baseline)} HCCs)")
    if m_baseline:
        for b in m_baseline:
            print(f"    * HCC {b['hcc_v28']:>3s}: {b['hcc_description']}")
            print(f"      Codes: {b['baseline_diagnosis_codes']} | Claims: {b['baseline_claim_count']} | Range: {b['first_baseline_date']} -> {b['last_baseline_date']}")
    else:
        print("    (No historical HCCs documented in 2021-2022)")

    print(f"\n  [ Review Candidates / Suspects ] ({len(m_suspects)} opportunities)")
    if m_suspects:
        for s in m_suspects:
            print(f"    * [{s['suspect_type']}] HCC {s['hcc_v28']:>3s}: {s['hcc_description']}")
            print(f"      Score: {s['priority_score']} (Recency={s['recency_score']}, Freq={s['frequency_score']}, Persist={s['persistence_score']}, Div={s['diversity_score']})")
            print(f"      Evidence: {s['supporting_diagnosis_codes']} ({s['evidence_count']} events) | Date Range: {s['first_evidence_date']} -> {s['last_evidence_date']}")
    else:
        print("    (No candidate review opportunities for this member)")

    load_tl = input("\nFetch and display full medical timeline for this member? [y/N]: ").strip().lower()
    if load_tl == "y":
        print("\nStreaming medical timeline from disk (searching 23M+ rows)...")
        events = get_member_timeline(query)
        print(f"Retrieved {len(events):,} chronological medical events:")
        print("-" * 78)
        print(f"{'Date':<12s} {'Type':<14s} {'Code':<10s} {'HCC':<8s} {'Source':<12s} {'Claim/PDE ID'}")
        print("-" * 78)
        for e in events[:50]:
            hcc_disp = f"HCC {e['hcc_v28']}" if e["hcc_v28"] else "-"
            print(f"{e['event_date']:<12s} {e['event_type']:<14s} {e['code']:<10s} {hcc_disp:<8s} {e['source']:<12s} {e['claim_id']}")
        if len(events) > 50:
            print(f"... and {len(events) - 50} more events")

    input("\nPress [Enter] to return...")


# ── View 3: Browse Candidates Queue ────────────────────────────────────────────

def browse_candidates(suspects, decisions):
    print_header("BROWSE HCC REVIEW OPPORTUNITIES QUEUE")
    print("Filter options:")
    print("  [1] All Opportunities (4,294 total)")
    print("  [2] Emerging HCCs only (Type A - 148 candidates)")
    print("  [3] Recapture Opportunities only (Type B - 4,146 candidates)")
    print("  [4] High Priority Only (Score >= 0.75)")
    print("  [5] Filter by specific HCC (e.g. 329, 38, 228)")

    opt = input("\nSelect filter [1-5]: ").strip()

    filtered = suspects
    if opt == "2":
        filtered = [s for s in suspects if s["suspect_type"] == "EMERGING"]
    elif opt == "3":
        filtered = [s for s in suspects if s["suspect_type"] == "RECAPTURE"]
    elif opt == "4":
        filtered = [s for s in suspects if float(s["priority_score"]) >= 0.75]
    elif opt == "5":
        hcc_q = input("Enter HCC number (e.g. 329): ").strip()
        filtered = [s for s in suspects if s["hcc_v28"] == hcc_q]

    # Sort by priority score descending
    filtered.sort(key=lambda x: float(x["priority_score"]), reverse=True)

    page_size = 15
    offset = 0

    while True:
        clear_screen()
        print_header(f"CANDIDATES QUEUE ({len(filtered):,} matched) - Page {offset // page_size + 1}")
        print(f"{'#':<4s} {'Suspect ID':<14s} {'Member ID':<18s} {'Type':<10s} {'HCC':<6s} {'Score':<6s} {'Diagnosis Codes':<18s} {'Decision'}")
        print("-" * 78)

        page_items = filtered[offset:offset + page_size]
        for idx, s in enumerate(page_items, offset + 1):
            dec = decisions.get(s["suspect_id"], {}).get("decision", "PENDING")
            codes_disp = s["supporting_diagnosis_codes"][:16] + ".." if len(s["supporting_diagnosis_codes"]) > 16 else s["supporting_diagnosis_codes"]
            print(f"{idx:<4d} {s['suspect_id']:<14s} {s['bene_id']:<18s} {s['suspect_type']:<10s} {s['hcc_v28']:<6s} {s['priority_score']:<6s} {codes_disp:<18s} {dec}")

        print("-" * 78)
        print("Commands: [N] Next Page | [P] Prev Page | [V <num>] View Details | [Q] Return Menu")
        cmd = input("\nEnter command: ").strip().lower()

        if cmd == "n" and offset + page_size < len(filtered):
            offset += page_size
        elif cmd == "p" and offset >= page_size:
            offset -= page_size
        elif cmd.startswith("v"):
            parts = cmd.split()
            if len(parts) == 2 and parts[1].isdigit():
                target_idx = int(parts[1]) - 1
                if 0 <= target_idx < len(filtered):
                    show_suspect_detail_card(filtered[target_idx], decisions)
        elif cmd == "q":
            break


def show_suspect_detail_card(s, decisions):
    print("\n" + "=" * 78)
    print(f"  POTENTIAL HCC REVIEW OPPORTUNITY CARD -- {s['suspect_id']}")
    print("=" * 78)
    print(f"  Member ID        : {s['bene_id']}")
    print(f"  Candidate HCC    : HCC {s['hcc_v28']} -- {s['hcc_description']}")
    print(f"  Suspect Type     : {s['suspect_type']}")
    print(f"  Priority Score   : {s['priority_score']} (Tier: {'HIGH' if float(s['priority_score'])>=0.75 else 'MEDIUM' if float(s['priority_score'])>=0.5 else 'LOW'})")
    print(f"  Score Breakdown  : Recency={s['recency_score']} | Frequency={s['frequency_score']} | Persistence={s['persistence_score']} | Diversity={s['diversity_score']}")
    print("-" * 78)
    print(f"  Supporting ICD-10: {s['supporting_diagnosis_codes']}")
    print(f"  Evidence Count   : {s['evidence_count']} event occurrences")
    print(f"  Date Span        : {s['first_evidence_date']} -> {s['last_evidence_date']}")
    print(f"  Clinical Sources : {s['sources']}")
    print(f"  Part D Rx Support: {s['has_prescription_support']}")
    print(f"  Sample Claim IDs : {s['supporting_claim_ids']}")
    print("-" * 78)
    dec = decisions.get(s["suspect_id"])
    if dec:
        print(f"  Audit Status     : {dec['decision']} (Logged at {dec['reviewer_timestamp']})")
        if dec.get("notes"):
            print(f"  Reviewer Notes   : {dec['notes']}")
    else:
        print(f"  Audit Status     : PENDING_REVIEW (Awaiting certified coder decision)")
    print("=" * 78)
    input("\nPress [Enter] to continue...")


# ── View 4: Interactive Reviewer Station ───────────────────────────────────────

def run_reviewer_station(suspects, decisions):
    # Filter pending only
    pending = [s for s in suspects if s["suspect_id"] not in decisions]

    # Sort high priority first
    pending.sort(key=lambda x: float(x["priority_score"]), reverse=True)

    if not pending:
        print_header("REVIEWER STATION")
        print("\nAll candidate opportunities have already been reviewed!")
        input("\nPress [Enter] to return...")
        return

    print_header(f"INTERACTIVE HUMAN REVIEWER STATION ({len(pending)} pending)")
    print("Review opportunities one-by-one. Your decisions are logged directly into data/review_decisions.csv.")
    input("\nPress [Enter] to start review session...")

    for idx, s in enumerate(pending, 1):
        clear_screen()
        print("=" * 78)
        print(f"  REVIEW QUEUE [{idx} of {len(pending)}] -- {s['suspect_id']}")
        print("=" * 78)
        print(f"  Member ID        : {s['bene_id']}")
        print(f"  Candidate HCC    : HCC {s['hcc_v28']} ({s['hcc_description']})")
        print(f"  Suspect Type     : {s['suspect_type']}")
        print(f"  Priority Score   : {s['priority_score']} (Recency={s['recency_score']}, Freq={s['frequency_score']}, Persist={s['persistence_score']}, Div={s['diversity_score']})")
        print("-" * 78)
        print(f"  Supporting ICD-10: {s['supporting_diagnosis_codes']}")
        print(f"  Evidence Events  : {s['evidence_count']} claims | Dates: {s['first_evidence_date']} -> {s['last_evidence_date']}")
        print(f"  Sources          : {s['sources']} | Prescription Support: {s['has_prescription_support']}")
        print(f"  Claim IDs        : {s['supporting_claim_ids']}")
        print("=" * 78)
        print("DECISION ACTIONS:")
        print("  [1] SUPPORT                (Agree that clinical documentation warrants HCC coding)")
        print("  [2] REJECT                 (Reject opportunity -- not clinically appropriate)")
        print("  [3] INSUFFICIENT_EVIDENCE  (Flag for secondary medical record retrieval)")
        print("  [S] Skip to next")
        print("  [Q] Quit session")

        action = input("\nEnter decision [1/2/3/S/Q]: ").strip().upper()

        if action == "1":
            notes = input("Optional reviewer notes: ").strip()
            save_decision(s, "SUPPORTED", notes)
            decisions[s["suspect_id"]] = {"decision": "SUPPORTED"}
            print(">> Logged decision: SUPPORTED")
        elif action == "2":
            notes = input("Optional reviewer notes: ").strip()
            save_decision(s, "NOT_SUPPORTED", notes)
            decisions[s["suspect_id"]] = {"decision": "NOT_SUPPORTED"}
            print(">> Logged decision: NOT_SUPPORTED")
        elif action == "3":
            notes = input("Optional reviewer notes: ").strip()
            save_decision(s, "INSUFFICIENT_EVIDENCE", notes)
            decisions[s["suspect_id"]] = {"decision": "INSUFFICIENT_EVIDENCE"}
            print(">> Logged decision: INSUFFICIENT_EVIDENCE")
        elif action == "Q":
            break


# ── Main Menu Loop ─────────────────────────────────────────────────────────────

def main():
    print("Loading risk adjustment dataset...")
    members   = load_members()
    suspects  = load_suspects()
    baseline  = load_baseline()

    while True:
        decisions = load_decisions()
        clear_screen()
        print("=" * 78)
        print("   UC03 -- RISK ADJUSTMENT & EVIDENCE-DRIVEN HCC SUSPECTING CONSOLE")
        print("=" * 78)
        print(f"  Active Dataset: 10,000 Members | 4,294 Suspect Candidates | {len(decisions)} Reviewed")
        print("-" * 78)
        print("  [1] Pipeline Overview & Summary Metrics")
        print("  [2] Search Member Profile & Timeline")
        print("  [3] Browse Candidates Queue (Filter by Type, Priority, or HCC)")
        print("  [4] Interactive Human Reviewer Station (Audit Logging)")
        print("  [5] Exit Console Application")
        print("=" * 78)

        choice = input("\nSelect option [1-5]: ").strip()

        if choice == "1":
            show_overview(members, suspects, baseline, decisions)
        elif choice == "2":
            show_member_search(members, suspects, baseline)
        elif choice == "3":
            browse_candidates(suspects, decisions)
        elif choice == "4":
            run_reviewer_station(suspects, decisions)
        elif choice == "5":
            print("\nExiting console application. Good luck with the project!\n")
            sys.exit(0)


if __name__ == "__main__":
    main()
