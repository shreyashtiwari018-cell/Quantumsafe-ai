"""
Sandbox smoke test (no FastAPI/uvicorn required — those need `pip install
-r requirements.txt` which needs network access). This exercises the same
logic app/main.py's endpoints call: seeding reports through the real
analyze_report() pipeline, persisting to SQLite with the real schema,
then running dashboard aggregation and pattern detection against it.

Run:
    python3 tests/smoke_test_pipeline.py
"""
import csv
import os
import sqlite3
import sys
import uuid

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.pipeline import analyze_report
from app.services.pattern_detection import detect_patterns

DATA_CSV = os.path.join(os.path.dirname(__file__), "..", "app", "data", "synthetic_reports.csv")
TEST_DB = os.path.join(os.path.dirname(__file__), "smoke_test.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS reports (
    report_id TEXT PRIMARY KEY,
    report_text TEXT NOT NULL,
    report_type TEXT,
    date TEXT,
    location TEXT,
    activity TEXT,
    hazard TEXT,
    sif_potential INTEGER,
    confidence REAL,
    risk_score INTEGER,
    risk_level TEXT,
    life_saving_rule TEXT,
    barrier_failure TEXT,
    status TEXT DEFAULT 'Open'
)
"""


def main():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    conn = sqlite3.connect(TEST_DB)
    conn.execute(SCHEMA)

    with open(DATA_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    print(f"Seeding {len(rows)} synthetic reports through the real analyze_report() pipeline...")
    mismatches = 0
    for row in rows:
        result = analyze_report(row["report_text"])
        report_id = f"R{uuid.uuid4().hex[:8].upper()}"
        conn.execute("""
            INSERT INTO reports
            (report_id, report_text, report_type, date, location, activity, hazard,
             sif_potential, confidence, risk_score, risk_level, life_saving_rule,
             barrier_failure, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Open')
        """, (
            report_id, row["report_text"], row["report_type"], row["date"], row["location"],
            result.activity, result.primary_hazard, int(result.sif_potential),
            result.confidence, result.risk_score, result.risk_level,
            result.life_saving_rule, ";".join(result.failed_barriers),
        ))
        if int(result.sif_potential) != int(row["sif_potential"]):
            mismatches += 1
    conn.commit()
    print(f"Seeded. Label mismatches vs synthetic ground truth: {mismatches}/{len(rows)}")

    # --- Dashboard summary check ---
    total = conn.execute("SELECT COUNT(*) c FROM reports").fetchone()[0]
    sif = conn.execute("SELECT COUNT(*) c FROM reports WHERE sif_potential = 1").fetchone()[0]
    critical = conn.execute("SELECT COUNT(*) c FROM reports WHERE risk_level = 'CRITICAL'").fetchone()[0]
    print(f"\n--- Dashboard summary ---\nTotal: {total} | SIF-potential: {sif} | Critical: {critical}")

    top_hazards = conn.execute("""
        SELECT hazard, COUNT(*) c FROM reports WHERE hazard IS NOT NULL
        GROUP BY hazard ORDER BY c DESC LIMIT 5
    """).fetchall()
    print("Top hazards:", top_hazards)

    # --- Pattern detection check ---
    conn.row_factory = sqlite3.Row
    all_rows = [dict(r) for r in conn.execute("SELECT * FROM reports").fetchall()]
    patterns = detect_patterns(all_rows, min_reports=3)
    print(f"\n--- Emerging patterns detected: {len(patterns)} ---")
    for p in patterns[:5]:
        print(f"  {p.hazard} @ {p.location} | barrier: {p.failed_barrier} | "
              f"{p.report_count} reports, {p.sif_count} SIF ({p.sif_ratio:.0%}), risk={p.risk}")

    conn.close()
    os.remove(TEST_DB)
    print("\nSmoke test complete — pipeline, persistence schema, dashboard aggregation, "
          "and pattern detection all executed successfully against 800 synthetic reports.")


if __name__ == "__main__":
    main()
