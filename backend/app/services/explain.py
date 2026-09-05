"""
Module 18: Explainable AI
Module 19: Recommendation Engine

Every SIF prediction must ship with human-readable reasons and an
advisory (not prescriptive) recommendation. Language is deliberately
hedged per spec section 31 (AI safety principle) — this is decision
support, not a verdict.
"""
from typing import List, Optional

RECOMMENDATIONS = {
    "CONFINED_SPACE": "Verify atmospheric testing, permit requirements, and standby arrangements before entry.",
    "WORKING_AT_HEIGHT": "Verify use and availability of appropriate fall-protection equipment and review work-at-height controls before continuation.",
    "ENERGY_ISOLATION": "Confirm lockout/tagout isolation has been applied and verified before work proceeds.",
    "HOT_WORK": "Confirm a valid hot work permit and active fire watch are in place before continuation.",
    "LINE_OF_FIRE": "Establish and maintain an exclusion zone; verify no personnel remain in the line of fire.",
    "VEHICLE": "Verify spotter presence and pedestrian/vehicle segregation before resuming vehicle movement.",
    "LIFTING": "Confirm rigging inspection and load chart compliance before continuing the lift.",
    "ELECTRICAL": "Verify de-energization and isolation of electrical equipment before further work.",
    "FIRE": "Remove ignition sources and reassess flammable material controls immediately.",
    "CHEMICAL": "Verify PPE and respiratory protection compliance before continuing the activity.",
    "PPE": "Reinforce PPE compliance requirements with site personnel.",
    "HOUSEKEEPING": "Schedule housekeeping remediation and barricade the affected area if not already done.",
}


def build_explanation(primary_hazard: Optional[str], matched_keywords: List[str],
                        failed_barriers: List[str], sif_potential: bool) -> List[str]:
    reasons = []
    if primary_hazard:
        label = primary_hazard.replace("_", " ").title()
        reasons.append(f"Report language matches known {label} precursor patterns")
    if failed_barriers:
        reasons.append(f"Indicated failure of critical control(s): {', '.join(failed_barriers)}")
    if sif_potential:
        reasons.append("Combination of hazard exposure and barrier failure elevates potential for severe consequence")
    if not reasons:
        reasons.append("No strong SIF precursor indicators detected in report language")
    return reasons


def build_recommendation(primary_hazard: Optional[str]) -> str:
    if not primary_hazard or primary_hazard not in RECOMMENDATIONS:
        return "Recommend standard HSE review of the reported condition."
    return RECOMMENDATIONS[primary_hazard] + " (Advisory only — not a substitute for qualified HSE judgment.)"
