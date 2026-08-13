# MVP Dataset Documentation

## 1. Executive Summary
This document provides complete documentation for the **5,000-member Minimum Viable Product (MVP) dataset** created for **UC03 – Risk Adjustment and HCC Suspecting Assistant**.

The dataset enables rapid hackathon development and testing of suspecting workflows without the overhead of production healthcare data warehouse infrastructure.

## 2. Selected Source Datasets
The MVP dataset was extracted strictly from the following CMS synthetic files:
1. `beneficiary_2023.csv`, `beneficiary_2024.csv`, `beneficiary_2025.csv` (Beneficiary Demographics & Enrollment)
2. `carrier.csv.xlsx` (Professional / Physician Claims)
3. `inpatient.csv` (Inpatient Hospital Claims)
4. `outpatient.csv` (Outpatient Hospital Claims)
5. `pde.csv` (Part D Prescription Drug Claims)
6. `2026 Final ICD-10-CM Mappings.xlsx` (CMS-HCC V28 Reference Mapping)

## 3. Selection Justification & Excluded Datasets
- **Included Sources**: Selected because inpatient, outpatient, carrier (physician), and Part D pharmacy claims represent the primary clinical evidence channels required for CMS-HCC V28 suspecting.
- **Excluded Datasets**:
  - `dme.csv` (Durable Medical Equipment)
  - `hha.csv` (Home Health Agency)
  - `hospice.csv` (Hospice Care)
  - `snf.csv` (Skilled Nursing Facility)
  - `Synthea` (Synthetic EHR Cohort)
- **Exclusion Justification**: Excluded to focus the MVP on core medical and pharmacy evidence, reduce dataset size, and maintain strict population isolation within CMS Medicare Fee-For-Service data.

## 4. Member Selection Methodology
- Exactly **5,000 unique member records** (`BENE_00001` through `BENE_05000`) were selected deterministically from the CMS beneficiary population.
- Each member represents an individual beneficiary record with complete demographic attributes (`birth_date`, `sex`, `state`).
- Claims and diagnosis events from Carrier, Inpatient, Outpatient, and PDE datasets were mapped deterministically to these 5,000 target members.

## 5. Output Summary & Record Counts

| MVP File | Target Path | Output Record Count | Description |
| --- | --- | --- | --- |
| `members.csv` | `data/mvp/members.csv` | **5,000** | Demographics for 5,000 target members |
| `claims.csv` | `data/mvp/claims.csv` | **2,220,878** | Medical claims (Carrier, Inpatient, Outpatient) & PDE prescription fills |
| `diagnoses.csv` | `data/mvp/diagnoses.csv` | **29,293,759** | Principal & secondary ICD-10 diagnosis codes |
| `hcc_mapping.csv` | `data/mvp/hcc_mapping.csv` | **11,870** | Official CMS-HCC V28 reference lookup table |

## 6. MVP CSV Column Definitions

### A. `members.csv`
- `member_id`: Deterministic member identifier (`BENE_00001` .. `BENE_05000`)
- `birth_date`: Date of birth in ISO format (`YYYY-MM-DD`)
- `sex`: Gender code (`1` = Male, `2` = Female)
- `state`: State location code

### B. `claims.csv`
- `member_id`: Foreign key link to `members.csv(member_id)`
- `claim_id`: Unique claim identifier (e.g. `CLM_INP_0000001`, `CLM_PDE_0000001`)
- `claim_type`: Claim domain (`CARRIER`, `INPATIENT`, `OUTPATIENT`, `PDE`)
- `service_date`: Claim service start date in ISO format (`YYYY-MM-DD`)

### C. `diagnoses.csv`
- `member_id`: Foreign key link to `members.csv(member_id)`
- `claim_id`: Foreign key link to `claims.csv(claim_id)`
- `diagnosis_code`: Cleaned uppercase ICD-10-CM diagnosis code (e.g. `E119`, `I10`)
- `diagnosis_date`: Date of service when diagnosis was billed (`YYYY-MM-DD`)
- `is_principal`: Boolean indicator (`True` if principal/admitting diagnosis, `False` if secondary)

### D. `hcc_mapping.csv`
- `diagnosis_code`: Cleaned uppercase ICD-10-CM diagnosis code
- `description`: Official ICD-10 diagnosis text description
- `hcc_v28`: CMS-HCC V28 model category number (e.g. `19`, `37`) or empty if unmapped
- `payment_2026`: Boolean flag (`True` if eligible for 2026 Payment Year)

## 7. System & Business Rule Alignment
- **Human-in-the-Loop Rule**: The MVP dataset provides raw clinical evidence for a human coder/clinician review and does not make final coding decisions or submit claims.
- **No Database / No Parquet**: All data is stored in plain CSV format under `data/mvp/`.
- **No Engine Code Yet**: No AI/suspecting models or risk score calculators were built.

## 8. Limitations
- Scoped to 5,000 members for hackathon execution speed.
- Unmapped ICD-10 codes remain empty in `hcc_v28` without artificial fallback.
