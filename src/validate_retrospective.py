"""
Retrospective Time-Shift Validation for the HCC Suspecting Engine

Strategy:
    Historical Baseline : 2019-2020   (what was documented)
    Current Evidence    : 2021        (new signals / dropped signals)
    Validation Ground   : 2022        (did the real world confirm our suspects?)

Metrics Produced:
    EMERGING suspects:
        Precision  = confirmed in 2022 / total flagged
        Recall     = confirmed in 2022 / all new HCCs that actually appeared in 2022

    RECAPTURE suspects:
        Recapture Rate = re-documented in 2022 / total flagged

    Scoring Calibration:
        SUPPORT rate per priority tier (high / medium / low)

Reads:
    data/member_timeline.csv   (23.8M events, streamed — not loaded into memory)
    data/hcc_mapping.csv       (for HCC descriptions)

Produces:
    data/validation_report.md
"""

import csv
import sys
from collections import defaultdict, Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR     = PROJECT_ROOT / "data"

TIMELINE_CSV    = DATA_DIR / "member_timeline.csv"
HCC_MAPPING_CSV = DATA_DIR / "hcc_mapping.csv"
OUT_REPORT      = DATA_DIR / "validation_report.md"

# Time-shifted windows
HIST_YEARS    = {"2019", "2020"}
CURRENT_YEAR  = "2021"
VALIDATE_YEAR = "2022"


def main():
    print("=" * 70)
    print("  Retrospective Time-Shift Validation")
    print(f"  Baseline: {sorted(HIST_YEARS)} | Current: {CURRENT_YEAR} | Validate: {VALIDATE_YEAR}")
    print("=" * 70)

    if not TIMELINE_CSV.exists():
        print(f"ERROR: Missing {TIMELINE_CSV}", file=sys.stderr)
        sys.exit(1)

    # Load HCC descriptions
    hcc_desc = {}
    if HCC_MAPPING_CSV.exists():
        with open(HCC_MAPPING_CSV, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                h = r["hcc_v28"].strip()
                if h and h not in hcc_desc:
                    hcc_desc[h] = r["description"].strip()

    # ── Pass 1: Stream timeline, accumulate per-member HCC sets by period ──
    print("\n[Step 1] Streaming 23.8M+ timeline events...")

    # member -> set of HCC codes per period
    hist_hccs    = defaultdict(set)   # 2019-2020
    curr_hccs    = defaultdict(set)   # 2021
    val_hccs     = defaultdict(set)   # 2022

    # For evidence scoring: member -> hcc -> list of dates in current period
    curr_evidence = defaultdict(lambda: defaultdict(list))
    # member -> hcc -> set of sources in current period
    curr_sources  = defaultdict(lambda: defaultdict(set))
    # member -> hcc -> set of all years seen (for persistence)
    hcc_all_years = defaultdict(lambda: defaultdict(set))

    total = 0
    with open(TIMELINE_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total += 1
            if row["event_type"] != "diagnosis":
                continue
            hcc = row["hcc_v28"]
            if not hcc:
                continue

            bene = row["bene_id"]
            yr   = row["event_date"][:4] if len(row["event_date"]) >= 4 else ""

            if yr:
                hcc_all_years[bene][hcc].add(yr)

            if yr in HIST_YEARS:
                hist_hccs[bene].add(hcc)
            elif yr == CURRENT_YEAR:
                curr_hccs[bene].add(hcc)
                curr_evidence[bene][hcc].append(row["event_date"])
                curr_sources[bene][hcc].add(row["source"])
            elif yr == VALIDATE_YEAR:
                val_hccs[bene].add(hcc)

            if total % 5_000_000 == 0:
                print(f"  ... {total:,} events processed")

    print(f"  Finished streaming {total:,} events")

    all_members = set(hist_hccs.keys()) | set(curr_hccs.keys()) | set(val_hccs.keys())
    print(f"  Members with any HCC data: {len(all_members):,}")

    # ── Pass 2: Generate suspects and validate ──
    print("\n[Step 2] Generating suspects and validating against {VALIDATE_YEAR}...")

    # EMERGING: in 2021, not in 2019-2020
    emerging_suspects = []
    # RECAPTURE: in 2019-2020, not in 2021
    recapture_suspects = []

    for bene in sorted(all_members):
        h_set = hist_hccs.get(bene, set())
        c_set = curr_hccs.get(bene, set())
        v_set = val_hccs.get(bene, set())

        # Emerging
        for hcc in sorted(c_set - h_set):
            dates = sorted(curr_evidence[bene][hcc])
            evidence_count = len(dates)
            last_date = dates[-1] if dates else ""

            # Score (same logic as build_hcc_suspects.py)
            recency = 1.0 if last_date >= f"{CURRENT_YEAR}-07-01" else (0.7 if last_date >= f"{CURRENT_YEAR}-01-01" else 0.3)
            frequency = min(evidence_count / 5.0, 1.0)
            years_seen = hcc_all_years[bene][hcc]
            persistence = 1.0 if len(years_seen) >= 2 else 0.5
            diversity = 0.5  # simplified — no Rx check in validation pass
            priority = round(0.30 * recency + 0.25 * frequency + 0.20 * persistence + 0.25 * diversity, 3)

            confirmed = hcc in v_set

            emerging_suspects.append({
                "bene_id": bene,
                "hcc": hcc,
                "evidence_count": evidence_count,
                "priority_score": priority,
                "confirmed_in_2022": confirmed,
                "sources": "|".join(sorted(curr_sources[bene][hcc])),
            })

        # Recapture
        for hcc in sorted(h_set - c_set):
            years_seen = hcc_all_years[bene][hcc]
            persistence = 1.0 if len(years_seen) >= 2 else 0.5
            recency = 0.7  # baseline period
            frequency = 0.5  # generic
            diversity = 0.5
            priority = round(0.30 * recency + 0.25 * frequency + 0.20 * persistence + 0.25 * diversity, 3)

            recaptured = hcc in v_set

            recapture_suspects.append({
                "bene_id": bene,
                "hcc": hcc,
                "priority_score": priority,
                "recaptured_in_2022": recaptured,
            })

    print(f"  Emerging suspects:  {len(emerging_suspects):,}")
    print(f"  Recapture suspects: {len(recapture_suspects):,}")

    # ── Metrics Calculation ──
    print("\n[Step 3] Computing validation metrics...")

    # --- EMERGING ---
    e_confirmed = sum(1 for s in emerging_suspects if s["confirmed_in_2022"])
    e_total     = len(emerging_suspects)
    e_precision = e_confirmed / e_total if e_total else 0

    # Recall: what fraction of genuinely new 2022 HCCs did we catch in 2021?
    # "New in 2022" = HCCs in 2022 that weren't in 2019-2020 baseline
    total_new_in_2022 = 0
    caught_in_2021 = 0
    for bene in all_members:
        h_set = hist_hccs.get(bene, set())
        c_set = curr_hccs.get(bene, set())
        v_set = val_hccs.get(bene, set())
        new_2022 = v_set - h_set  # HCCs new in 2022 relative to baseline
        total_new_in_2022 += len(new_2022)
        # How many of those did our 2021 emerging suspects catch?
        caught_in_2021 += len(new_2022 & (c_set - h_set))

    e_recall = caught_in_2021 / total_new_in_2022 if total_new_in_2022 else 0
    e_f1 = 2 * e_precision * e_recall / (e_precision + e_recall) if (e_precision + e_recall) else 0

    # --- RECAPTURE ---
    r_recaptured = sum(1 for s in recapture_suspects if s["recaptured_in_2022"])
    r_total      = len(recapture_suspects)
    r_rate       = r_recaptured / r_total if r_total else 0

    # --- SCORING CALIBRATION ---
    # For emerging suspects: confirmation rate by priority tier
    e_high   = [s for s in emerging_suspects if s["priority_score"] >= 0.75]
    e_med    = [s for s in emerging_suspects if 0.50 <= s["priority_score"] < 0.75]
    e_low    = [s for s in emerging_suspects if s["priority_score"] < 0.50]

    def conf_rate(lst, key="confirmed_in_2022"):
        return sum(1 for s in lst if s[key]) / len(lst) if lst else 0

    # For recapture: recapture rate by priority tier
    r_high   = [s for s in recapture_suspects if s["priority_score"] >= 0.75]
    r_med    = [s for s in recapture_suspects if 0.50 <= s["priority_score"] < 0.75]
    r_low    = [s for s in recapture_suspects if s["priority_score"] < 0.50]

    def recap_rate(lst):
        return sum(1 for s in lst if s["recaptured_in_2022"]) / len(lst) if lst else 0

    # --- TOP CONFIRMED HCCs ---
    confirmed_hccs = Counter(s["hcc"] for s in emerging_suspects if s["confirmed_in_2022"])
    top_confirmed = confirmed_hccs.most_common(10)

    # --- PRINT RESULTS ---
    print("\n" + "=" * 70)
    print("  VALIDATION RESULTS")
    print("=" * 70)

    print(f"\n  -- EMERGING HCC Suspects --")
    print(f"  Total flagged in {CURRENT_YEAR}          : {e_total:,}")
    print(f"  Confirmed in {VALIDATE_YEAR}             : {e_confirmed:,}")
    print(f"  Precision                        : {e_precision:.1%}")
    print(f"  Total new HCCs in {VALIDATE_YEAR}        : {total_new_in_2022:,}")
    print(f"  Caught by {CURRENT_YEAR} evidence        : {caught_in_2021:,}")
    print(f"  Recall                           : {e_recall:.1%}")
    print(f"  F1 Score                         : {e_f1:.3f}")

    print(f"\n  -- RECAPTURE Suspects --")
    print(f"  Total flagged                    : {r_total:,}")
    print(f"  Re-documented in {VALIDATE_YEAR}         : {r_recaptured:,}")
    print(f"  Recapture Rate                   : {r_rate:.1%}")

    print(f"\n  -- Scoring Calibration (Emerging) --")
    print(f"  HIGH   (>= 0.75): {len(e_high):>5,} suspects, confirmation rate = {conf_rate(e_high):.1%}")
    print(f"  MEDIUM (0.5-0.75): {len(e_med):>5,} suspects, confirmation rate = {conf_rate(e_med):.1%}")
    print(f"  LOW    (< 0.50):  {len(e_low):>5,} suspects, confirmation rate = {conf_rate(e_low):.1%}")

    print(f"\n  -- Scoring Calibration (Recapture) --")
    print(f"  HIGH   (>= 0.75): {len(r_high):>5,} suspects, recapture rate = {recap_rate(r_high):.1%}")
    print(f"  MEDIUM (0.5-0.75): {len(r_med):>5,} suspects, recapture rate = {recap_rate(r_med):.1%}")
    print(f"  LOW    (< 0.50):  {len(r_low):>5,} suspects, recapture rate = {recap_rate(r_low):.1%}")

    print(f"\n  -- Top Confirmed Emerging HCCs --")
    for hcc, cnt in top_confirmed:
        desc = hcc_desc.get(hcc, "Unknown")
        total_flagged = sum(1 for s in emerging_suspects if s["hcc"] == hcc)
        print(f"  HCC {hcc:>4s}: {cnt:>4,} confirmed / {total_flagged:>4,} flagged ({cnt/total_flagged:.0%})  {desc}")

    # ── Write Report ──
    print(f"\n[Step 4] Writing validation report...")

    report = f"""# Retrospective Validation Report

## Methodology

| Parameter | Value |
|---|---|
| **Historical Baseline** | {sorted(HIST_YEARS)} |
| **Current Evidence** | {CURRENT_YEAR} |
| **Validation Ground Truth** | {VALIDATE_YEAR} |
| **Members with HCC Data** | {len(all_members):,} |
| **Total Timeline Events Processed** | {total:,} |

---

## Emerging HCC Suspect Performance

The engine flagged HCC categories appearing in {CURRENT_YEAR} evidence that had NO documentation in {sorted(HIST_YEARS)}.
We then checked whether those same HCCs were documented in {VALIDATE_YEAR} (ground truth confirmation).

| Metric | Value |
|---|---|
| **Suspects Flagged** | {e_total:,} |
| **Confirmed in {VALIDATE_YEAR}** | {e_confirmed:,} |
| **Precision** | **{e_precision:.1%}** |
| **Total New HCCs in {VALIDATE_YEAR}** | {total_new_in_2022:,} |
| **Caught by Engine** | {caught_in_2021:,} |
| **Recall** | **{e_recall:.1%}** |
| **F1 Score** | **{e_f1:.3f}** |

---

## Recapture Opportunity Performance

The engine flagged HCCs documented in the {sorted(HIST_YEARS)} baseline that were MISSING from {CURRENT_YEAR} evidence.
We checked whether those HCCs reappeared in {VALIDATE_YEAR}.

| Metric | Value |
|---|---|
| **Recapture Suspects Flagged** | {r_total:,} |
| **Re-documented in {VALIDATE_YEAR}** | {r_recaptured:,} |
| **Recapture Rate** | **{r_rate:.1%}** |

---

## Scoring Calibration

### Emerging HCC — Confirmation Rate by Priority Tier

| Priority Tier | Suspects | Confirmed | Confirmation Rate |
|---|---|---|---|
| **HIGH** (>= 0.75) | {len(e_high):,} | {sum(1 for s in e_high if s['confirmed_in_2022']):,} | **{conf_rate(e_high):.1%}** |
| **MEDIUM** (0.50-0.75) | {len(e_med):,} | {sum(1 for s in e_med if s['confirmed_in_2022']):,} | **{conf_rate(e_med):.1%}** |
| **LOW** (< 0.50) | {len(e_low):,} | {sum(1 for s in e_low if s['confirmed_in_2022']):,} | **{conf_rate(e_low):.1%}** |

### Recapture — Recapture Rate by Priority Tier

| Priority Tier | Suspects | Recaptured | Recapture Rate |
|---|---|---|---|
| **HIGH** (>= 0.75) | {len(r_high):,} | {sum(1 for s in r_high if s['recaptured_in_2022']):,} | **{recap_rate(r_high):.1%}** |
| **MEDIUM** (0.50-0.75) | {len(r_med):,} | {sum(1 for s in r_med if s['recaptured_in_2022']):,} | **{recap_rate(r_med):.1%}** |
| **LOW** (< 0.50) | {len(r_low):,} | {sum(1 for s in r_low if s['recaptured_in_2022']):,} | **{recap_rate(r_low):.1%}** |

---

## Top Confirmed Emerging HCCs

| HCC | Description | Confirmed | Flagged | Confirmation Rate |
|---|---|---|---|---|
"""
    for hcc, cnt in top_confirmed:
        desc = hcc_desc.get(hcc, "Unknown")
        total_flagged = sum(1 for s in emerging_suspects if s["hcc"] == hcc)
        report += f"| **HCC {hcc}** | {desc} | {cnt:,} | {total_flagged:,} | **{cnt/total_flagged:.0%}** |\n"

    report += """
---

## Interpretation

- **Precision** measures: "When we flag a suspect, how often is it real?"
- **Recall** measures: "Of all real new HCCs, how many did we catch early?"
- **Scoring calibration** confirms: "Do higher scores correlate with higher confirmation?"
- **Recapture rate** measures: "Of dropped HCCs, how many actually return?"

> [!NOTE]
> These metrics use documentation presence in claims as a proxy for clinical truth.
> A confirmed suspect means the HCC code appeared in actual claims during the validation year.
> This is the closest available approximation to ground truth in administrative claims data.
"""

    with open(OUT_REPORT, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"  Written: {OUT_REPORT}")

    print("\n" + "=" * 70)
    print("  VALIDATION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
