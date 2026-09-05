"""
Module 5: Risk Scoring.

Produces a transparent, explainable 0-100 risk score from extracted
signals. This is OUR prototype scoring framework, not an official OIL
methodology — never present these thresholds as OIL-certified.
"""
from dataclasses import dataclass
from typing import List, Optional
from app.data.taxonomy import HAZARD_LEXICON, RISK_LEVELS


@dataclass
class RiskResult:
    score: int
    level: str
    breakdown: dict


def score_risk(primary_hazard: Optional[str], sif_potential: bool,
               classifier_confidence: float, failed_barriers: List[str]) -> RiskResult:
    if not primary_hazard:
        base_severity = 8
    else:
        base_severity = HAZARD_LEXICON[primary_hazard]["severity"] * 7  # 0-63ish

    barrier_penalty = min(20, len(failed_barriers) * 10)
    sif_weight = 12 if sif_potential else 0
    confidence_adj = round((classifier_confidence - 0.5) * 16)  # -8..+8

    raw = base_severity * (1.0 if sif_potential else 0.5) + barrier_penalty + sif_weight + confidence_adj
    score = max(0, min(100, int(raw)))

    level = "LOW"
    for lo, hi, name in RISK_LEVELS:
        if lo <= score <= hi:
            level = name
            break

    breakdown = {
        "base_severity": base_severity,
        "barrier_penalty": barrier_penalty,
        "sif_weight": sif_weight,
        "confidence_adjustment": confidence_adj,
    }
    return RiskResult(score=score, level=level, breakdown=breakdown)
