from pathlib import Path
import psycopg

values = {}
for line in (Path("backend/.env")).read_text(encoding="utf-8").splitlines():
    key, separator, value = line.partition("=")
    if separator:
        values[key.strip()] = value.strip()

connection = psycopg.connect(
    host=values["DB_HOST"], port=values["DB_PORT"], dbname=values["DB_NAME"],
    user=values["DB_USER"], password=values["DB_PASSWORD"], sslmode="require",
    connect_timeout=15,
)
tables = [
    "alembic_version", "members", "claims", "member_timeline", "suspects",
    "suspect_evidence", "llm_reviews", "review_decisions", "pipeline_runs",
]
with connection.cursor() as cursor:
    for table in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            print(f"{table}: {cursor.fetchone()[0]}")
        except Exception as error:
            connection.rollback()
            print(f"{table}: ERROR {type(error).__name__}: {error}")
connection.close()
