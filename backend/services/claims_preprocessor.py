"""
CMS Raw Claims Preprocessing Service.

Processes a ZIP archive containing pipe-delimited CMS claims files:
  inpatient.csv   - INPATIENT claims  (up to 25 ICD diagnosis columns)
  outpatient.csv  - OUTPATIENT claims (up to 25 ICD diagnosis columns)
  carrier.csv     - CARRIER claims    (up to 12 ICD diagnosis columns)
  pde.csv         - Part D prescription events [optional]

Each wide-format CMS claim row is exploded into individual per-diagnosis rows.
All date and code fields are cleaned and normalized before ingestion.
"""

import csv
import io
import uuid
import zipfile
from typing import Dict, List, Optional, Tuple

# Month abbreviation -> zero-padded number (for DD-Mon-YYYY parsing)
_MONTHS: Dict[str, str] = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "may": "05", "jun": "06", "jul": "07", "aug": "08",
    "sep": "09", "oct": "10", "nov": "11", "dec": "12",
}

# (filename, source_label, max_icd_columns)
_DIAGNOSIS_FILE_CONFIGS = [
    ("inpatient.csv",  "INPATIENT",  25),
    ("outpatient.csv", "OUTPATIENT", 25),
    ("carrier.csv",    "CARRIER",    12),
]


# ── Date / Code Cleaning ───────────────────────────────────────────────────────

def _clean_date(raw: object) -> Optional[str]:
    """Normalize a raw date string to YYYY-MM-DD, or None if unparseable.

    Handles:
      - YYYY-MM-DD    (pass-through, e.g. 2026-01-15)
      - DD-Mon-YYYY   (e.g. 15-Jan-2026, format CMS uses in LDS files)
    """
    text = str(raw or "").strip()
    if not text or text.upper() in {"NULL", "NONE", "NAN", "NA"}:
        return None
    # Already ISO format: YYYY-MM-DD
    if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
        return text[:10]
    # DD-Mon-YYYY format
    parts = text.split("-")
    if len(parts) == 3:
        day, mon, year = parts[0].strip(), parts[1].strip(), parts[2].strip()
        mon_num = _MONTHS.get(mon.lower())
        if mon_num and year:
            if len(year) == 2:
                year = "19" + year if int(year) > 50 else "20" + year
            return f"{year}-{mon_num}-{day.zfill(2)}"
    return None


def _clean_code(raw: object) -> Optional[str]:
    """Normalize an ICD-10 code: uppercase, strip whitespace, remove dots."""
    text = str(raw or "").strip().upper().replace(".", "")
    return text if text and text not in {"NULL", "NONE", "NAN", "NA"} else None


# ── Diagnosis Extraction ───────────────────────────────────────────────────────

def _normalize_diagnosis_file(
    csv_bytes: bytes,
    source: str,
    max_icd: int,
) -> Tuple[List[Dict], int, int]:
    """
    Explode a wide-format pipe-delimited CMS claims file into individual
    diagnosis event rows (one row per unique diagnosis code per claim).

    CMS column mapping:
      BENE_ID         -> bene_id
      CLM_ID          -> claim_id base (line suffix added for uniqueness)
      CLM_FROM_DT     -> claim_date
      PRNCPAL_DGNS_CD -> diagnosis_code (is_principal = True)
      ICD_DGNS_CD1-N  -> diagnosis_code (is_principal = False, deduped)

    claim_id is made line-unique: {SOURCE}_{CLM_ID}_P / _{1..N}
    to satisfy the (batch_id, claim_id) unique constraint in the claims table.

    Returns:
        rows          - List of normalized claim dicts
        total_claims  - Count of raw CMS claim rows processed
        skipped       - Count of rows skipped (missing bene_id)
    """
    rows: List[Dict] = []
    total_claims = 0
    skipped = 0

    text = csv_bytes.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text), delimiter="|")

    for row in reader:
        bene_id = str(row.get("BENE_ID") or "").strip()
        clm_id  = str(row.get("CLM_ID")  or "").strip()
        # CLM_FROM_DT is the admission/service start date; fall back to CLM_THRU_DT
        raw_date   = (row.get("CLM_FROM_DT") or row.get("CLM_THRU_DT") or "").strip()
        claim_date = _clean_date(raw_date)

        if not bene_id:
            skipped += 1
            continue

        total_claims += 1
        seen_codes: set = set()

        # ── Principal diagnosis ──────────────────────────────────────────────
        p_code = _clean_code(row.get("PRNCPAL_DGNS_CD"))
        if p_code:
            rows.append({
                "bene_id":        bene_id,
                "claim_id":       f"{source}_{clm_id}_P" if clm_id else None,
                "claim_date":     claim_date,
                "diagnosis_code": p_code,
                "source":         source,
                "is_principal":   True,
            })
            seen_codes.add(p_code)

        # ── Secondary diagnoses: ICD_DGNS_CD1 .. ICD_DGNS_CDN ───────────────
        for i in range(1, max_icd + 1):
            col    = f"ICD_DGNS_CD{i}"
            s_code = _clean_code(row.get(col))
            if s_code and s_code not in seen_codes:
                rows.append({
                    "bene_id":        bene_id,
                    "claim_id":       f"{source}_{clm_id}_{i}" if clm_id else None,
                    "claim_date":     claim_date,
                    "diagnosis_code": s_code,
                    "source":         source,
                    "is_principal":   False,
                })
                seen_codes.add(s_code)

    return rows, total_claims, skipped


# ── Prescription (PDE) Extraction ─────────────────────────────────────────────

def _normalize_pde_file(csv_bytes: bytes) -> List[Dict]:
    """
    Extract Part D prescription events from a PDE pipe-delimited file.

    CMS column mapping:
      BENE_ID      -> bene_id
      PDE_ID       -> pde_id  (also used to build event_id)
      SRVC_DT      -> event_date
      PROD_SRVC_ID -> drug_code (NDC — National Drug Code)
    """
    rows: List[Dict] = []
    text = csv_bytes.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text), delimiter="|")

    for row in reader:
        bene_id    = str(row.get("BENE_ID")       or "").strip()
        pde_id     = str(row.get("PDE_ID")         or "").strip()
        drug_code  = str(row.get("PROD_SRVC_ID")   or "").strip() or None
        event_date = _clean_date(row.get("SRVC_DT"))

        if not bene_id:
            continue

        # event_id is PK — generate UUID fallback if PDE_ID is missing
        event_id = f"PDE_{pde_id}" if pde_id else f"PDE_AUTO_{uuid.uuid4().hex[:12]}"

        rows.append({
            "event_id":   event_id,
            "bene_id":    bene_id,
            "pde_id":     pde_id or None,
            "event_date": event_date,
            "drug_code":  drug_code,
        })

    return rows


# ── Public Entry Point ─────────────────────────────────────────────────────────

def preprocess_claims_zip(
    zip_bytes: bytes,
) -> Tuple[List[Dict], List[Dict], Dict[str, int]]:
    """
    Extract and normalize a ZIP archive containing CMS claims files.

    Accepts any combination of:
      inpatient.csv, outpatient.csv, carrier.csv  (at least one required)
      pde.csv                                      (optional)

    File matching is case-insensitive. Subdirectory paths inside the ZIP
    are ignored (only the basename is matched).

    Returns:
        claim_rows  - Normalized claim dicts ready for ingest_claim_rows()
        pde_rows    - Prescription event dicts for events_prescription
        stats       - Row counts keyed by source:
                      e.g. {"INPATIENT": 800, "CARRIER": 1200, "PDE": 400,
                             "raw_claims": 2000, "diagnosis_rows": 7500}

    Raises:
        ValueError  - If bytes are not a valid ZIP or no claim file found.
    """
    buf = io.BytesIO(zip_bytes)
    if not zipfile.is_zipfile(buf):
        raise ValueError(
            "Uploaded file is not a valid ZIP archive. "
            "Please upload a .zip file containing your CMS claims CSVs."
        )

    buf.seek(0)
    zf = zipfile.ZipFile(buf)

    # Build case-insensitive basename -> full zip path mapping
    name_map: Dict[str, str] = {}
    for entry in zf.namelist():
        if entry.endswith("/"):
            continue  # skip directory entries
        basename = entry.lower().rsplit("/", 1)[-1]
        name_map[basename] = entry

    # Validate at least one diagnosis file is present
    found = [fname for fname, _, _ in _DIAGNOSIS_FILE_CONFIGS if fname in name_map]
    if not found:
        raise ValueError(
            "ZIP must contain at least one of: inpatient.csv, outpatient.csv, carrier.csv. "
            f"Files found in ZIP: {sorted(name_map.keys()) or '(empty)'}"
        )

    all_claim_rows: List[Dict] = []
    pde_rows:       List[Dict] = []
    stats:          Dict[str, int] = {}
    total_raw_claims = 0

    # ── Process each diagnosis file present ─────────────────────────────────
    for filename, source, max_icd in _DIAGNOSIS_FILE_CONFIGS:
        if filename not in name_map:
            continue
        csv_bytes    = zf.read(name_map[filename])
        rows, n_claims, n_skipped = _normalize_diagnosis_file(csv_bytes, source, max_icd)
        all_claim_rows.extend(rows)
        stats[source]                    = len(rows)           # exploded diagnosis rows
        stats[f"{source}_raw_claims"]    = n_claims            # original CMS claim rows
        stats[f"{source}_skipped"]       = n_skipped           # rows missing BENE_ID
        total_raw_claims                += n_claims

    stats["raw_claims_total"]   = total_raw_claims
    stats["diagnosis_rows_total"] = len(all_claim_rows)

    # ── Process PDE prescriptions (optional) ────────────────────────────────
    if "pde.csv" in name_map:
        pde_csv_bytes = zf.read(name_map["pde.csv"])
        pde_rows      = _normalize_pde_file(pde_csv_bytes)
        stats["PDE"]  = len(pde_rows)

    return all_claim_rows, pde_rows, stats
