# Medicare Advantage Risk Adjustment and HCC Documentation Review Assistant

An evidence-driven decision-support platform for Medicare Advantage risk adjustment and CMS-HCC V28 documentation review.

---

## PostgreSQL Database & SQLAlchemy Data Access Layer

This repository includes a production-ready PostgreSQL database architecture built using Python, SQLAlchemy 2.x, `psycopg`, and Alembic.

### 1. Database Prerequisites & Setup

Ensure PostgreSQL is installed and running on your system (or accessible remotely).

Create the target PostgreSQL database:
```sql
CREATE DATABASE hcc_review_db;
```

### 2. Environment Configuration

Copy or create a `.env` file in the project root directory and set your PostgreSQL connection string:

```env
DATABASE_URL=postgresql+psycopg://postgres:your_password@localhost:5432/hcc_review_db
```

> **Note**: Do NOT commit credentials to version control. The application reads `DATABASE_URL` dynamically from the environment.

### 3. Database Schema & Source Mapping

| Source CSV File | Database Table | Primary Key | Key Relationships |
|---|---|---|---|
| `data/members.csv` | `members` | `bene_id` | Master beneficiary registry |
| `data/hcc_mapping.csv` | `hcc_mappings` | `diagnosis_code` | CMS-HCC V28 reference lookup crosswalk |
| `data/events_diagnosis.csv` | `events_diagnosis` | `event_id` | FK -> `members.bene_id` |
| `data/events_prescription.csv` | `events_prescription` | `event_id` | FK -> `members.bene_id` |
| `data/member_timeline.csv` | `member_timeline` | `id` (autoincrement) | FK -> `members.bene_id` |
| `data/member_hcc_baseline.csv` | `member_hcc_baseline` | `id` (autoincrement) | FK -> `members.bene_id` |
| `data/suspects.csv` | `suspects` | `suspect_id` | FK -> `members.bene_id` |
| `data/review_decisions.csv` | `review_decisions` | `id` (autoincrement) | FK -> `suspects.suspect_id`, `members.bene_id` |
| Rejection Log | `ingestion_rejections` | `id` (autoincrement) | Tracks invalid/corrupted records |

### 4. Running Database Migrations (Alembic)

To apply the database schema via Alembic migrations:

```bash
# Upgrade to latest database schema
python -m alembic upgrade head
```

To create a new migration if model definitions change in `src/database/models.py`:
```bash
python -m alembic revision --autogenerate -m "describe_changes"
```

### 5. Running the Data Ingestion Pipeline

To load prepared datasets from `data/` into PostgreSQL:

```bash
python src/database/ingest.py
```

Features of the ingestion script:
- Streamed batch loading (`CHUNK_SIZE=50,000`) for high performance on multi-gigabyte files.
- Deduplication and primary key validation.
- Invalid records logged to `ingestion_rejections` table rather than failing silently.
- Repeatable execution (safe to re-run).

### 6. Verifying Data Loading

To run the post-ingestion database integrity test suite:

```bash
python src/database/validate.py
```

The validation suite verifies:
1. Row counts across all 9 database tables.
2. Null checks on primary keys and foreign keys.
3. Duplicate primary key checks.
4. Foreign key referential integrity (checking for orphan events/suspects).
5. ICD-10 to CMS-HCC V28 crosswalk mapping coverage.

### 7. Generating an LLM Reviewer Summary

The pipeline stores an evidence JSON payload for each generated suspect in the
`llm_reviews` table. To turn that payload into an evidence-grounded text summary
for a human reviewer, configure the following environment variables:

```env
OPENAI_API_KEY=your_api_key
OPENAI_MODEL=gpt-5.6
```

After a claims batch creates an `llm_reviews` record, call:

```http
POST /api/llm-reviews/{review_id}/generate
```

The endpoint submits only the stored evidence JSON to the configured model and
saves the structured model output in `output_payload` and the human-readable text
in `reviewer_summary`. The generated summary is decision support only; a qualified
human must review the source record and make any coding decision.
