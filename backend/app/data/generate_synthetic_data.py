"""
Generates a synthetic dataset of industrial safety reports for prototype
development ONLY. This is NOT real OIL data — never present it as such.

Run:
    python -m app.data.generate_synthetic_data

Produces: app/data/synthetic_reports.csv
Schema matches project spec section 16 (dataset schema).
"""
import csv
import random
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from app.data.taxonomy import HAZARD_LEXICON, BARRIERS, REPORT_TYPES

random.seed(42)

LOCATIONS = ["Site A", "Site B", "Site C - Refinery", "Well Pad 12", "Tank Farm 3",
             "Pipeline Section 7", "Loading Terminal", "Maintenance Yard"]

# Template bank: (hazard_key, sif_potential, template_text)
TEMPLATES = [
    ("CONFINED_SPACE", 1, "Worker entered confined space without atmospheric testing. No standby person was present."),
    ("CONFINED_SPACE", 1, "Technician performed vessel entry without gas testing during maintenance shutdown."),
    ("CONFINED_SPACE", 0, "Confined space entry was performed with atmospheric testing completed and standby person present."),
    ("WORKING_AT_HEIGHT", 1, "Worker was observed working at height without a safety harness on the scaffold."),
    ("WORKING_AT_HEIGHT", 1, "Improper scaffolding was noted with no guardrail installed at elevated platform."),
    ("WORKING_AT_HEIGHT", 0, "Worker was seen working at height with harness properly secured and scaffold inspected."),
    ("ENERGY_ISOLATION", 1, "Technician worked on equipment without lockout tagout isolation performed, energized equipment nearby."),
    ("ENERGY_ISOLATION", 0, "Maintenance was carried out after proper lockout tagout isolation was verified."),
    ("HOT_WORK", 1, "Hot work welding was performed without a fire watch permit in a flammable atmosphere area."),
    ("HOT_WORK", 0, "Hot work permit and fire watch were in place during welding activity."),
    ("LINE_OF_FIRE", 1, "Worker was standing under a suspended load during lifting operation, no exclusion zone maintained."),
    ("LINE_OF_FIRE", 0, "Exclusion zone was maintained and no personnel were in line of fire during the lift."),
    ("VEHICLE", 1, "Vehicle reversed near pedestrian walkway without a spotter and narrowly missed a worker."),
    ("VEHICLE", 0, "Vehicle reversing was conducted with a spotter present and pedestrian path segregated."),
    ("LIFTING", 1, "Crane lifting operation proceeded with a sling that was not inspected, rigging appeared worn."),
    ("LIFTING", 0, "Lifting operation followed load chart with rigging inspected prior to lift."),
    ("ELECTRICAL", 1, "Electrical panel was left open with exposed live wire near walking path."),
    ("ELECTRICAL", 0, "Electrical panel was properly closed and de-energized before inspection."),
    ("FIRE", 1, "Gas leak was detected near an ignition source with flammable material nearby."),
    ("FIRE", 0, "Minor gas odor was reported and area was isolated with no ignition sources present."),
    ("CHEMICAL", 1, "Worker was exposed to chemical spill without wearing respirator or protective equipment."),
    ("CHEMICAL", 0, "Chemical handling was performed with full PPE and respirator worn as required."),
    ("PPE", 0, "Worker was not wearing safety glasses in the workshop area."),
    ("HOUSEKEEPING", 0, "Oil spill was observed near the maintenance area. Area was barricaded and cleaned immediately."),
    ("HOUSEKEEPING", 0, "Cluttered walkway with minor trip hazard was reported near the warehouse."),
]

REPORT_ID = 1


def build_row(hazard_key, sif_flag, text, rid):
    hazard_info = HAZARD_LEXICON[hazard_key]
    barrier_entries = BARRIERS.get(hazard_key, [])
    barrier_names = ";".join(b["barrier"] for b in barrier_entries) if sif_flag else ""

    base_severity = hazard_info["severity"] * 10
    exposure = random.randint(5, 15)
    barrier_penalty = 20 if sif_flag else 0
    recurrence = random.randint(0, 10)
    risk_score = min(100, base_severity * (0.55 if not sif_flag else 1.0) + exposure + barrier_penalty + recurrence)
    risk_score = int(risk_score)

    if risk_score <= 30:
        risk_level = "LOW"
    elif risk_score <= 60:
        risk_level = "MEDIUM"
    elif risk_score <= 80:
        risk_level = "HIGH"
    else:
        risk_level = "CRITICAL"

    return {
        "report_id": f"R{rid:04d}",
        "report_text": text,
        "report_type": random.choice(REPORT_TYPES) if not sif_flag else random.choice(["UNSAFE_ACT", "NEAR_MISS", "INCIDENT"]),
        "date": f"2026-{random.randint(1,8):02d}-{random.randint(1,28):02d}",
        "location": random.choice(LOCATIONS),
        "activity": hazard_key.replace("_", " ").title(),
        "hazard": hazard_key,
        "barrier_failure": barrier_names,
        "life_saving_rule": hazard_info["life_saving_rule"],
        "sif_potential": sif_flag,
        "risk_score": risk_score,
        "risk_level": risk_level,
    }


def generate(n=800):
    rows = []
    rid = 1
    # Weighted sampling with slight noise so it's not perfectly repetitive
    for _ in range(n):
        hazard_key, sif_flag, text = random.choice(TEMPLATES)
        rows.append(build_row(hazard_key, sif_flag, text, rid))
        rid += 1
    return rows


def main():
    rows = generate(800)
    out_path = os.path.join(os.path.dirname(__file__), "synthetic_reports.csv")
    fieldnames = list(rows[0].keys())
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    sif_count = sum(r["sif_potential"] for r in rows)
    print(f"Wrote {len(rows)} synthetic reports to {out_path}")
    print(f"SIF-potential: {sif_count} | Non-SIF: {len(rows) - sif_count}")


if __name__ == "__main__":
    main()
