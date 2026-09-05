"""
The end-to-end Phase 1 pipeline: report text in -> full structured
analysis out. This is the single function the API layer calls, and the
one both the FastAPI route and any test/CLI script should use, so the
API contract stays consistent no matter how it's invoked.
"""
from dataclasses import dataclass, asdict
from typing import List

from app.services.extraction import extract, detect_barrier_failures
from app.services.classifier import classify
from app.services.risk_engine import score_risk
from app.services.explain import build_explanation, build_recommendation


@dataclass
class AnalysisResult:
    report_text: str
    sif_potential: bool
    confidence: float
    classification_method: str
    risk_score: int
    risk_level: str
    risk_breakdown: dict
    primary_hazard: str
    activity: str
    life_saving_rule: str
    failed_barriers: List[str]
    explanation: List[str]
    recommendation: str

    def to_dict(self):
        return asdict(self)


def analyze_report(text: str) -> AnalysisResult:
    extraction = extract(text)
    failed_barriers = detect_barrier_failures(text, extraction.primary_hazard)

    classification = classify(text, extraction.matched_hazards, failed_barriers)

    risk = score_risk(
        primary_hazard=extraction.primary_hazard,
        sif_potential=classification.sif_potential,
        classifier_confidence=classification.confidence,
        failed_barriers=failed_barriers,
    )

    explanation = build_explanation(
        primary_hazard=extraction.primary_hazard,
        matched_keywords=extraction.matched_keywords,
        failed_barriers=failed_barriers,
        sif_potential=classification.sif_potential,
    )
    recommendation = build_recommendation(extraction.primary_hazard)

    hazard_label = extraction.primary_hazard.replace("_", " ").title() if extraction.primary_hazard else "Unclassified"

    return AnalysisResult(
        report_text=text,
        sif_potential=classification.sif_potential,
        confidence=round(classification.confidence, 3),
        classification_method=classification.method,
        risk_score=risk.score,
        risk_level=risk.level,
        risk_breakdown=risk.breakdown,
        primary_hazard=hazard_label,
        activity=hazard_label,
        life_saving_rule=extraction.life_saving_rule or "Not Determined",
        failed_barriers=failed_barriers,
        explanation=explanation,
        recommendation=recommendation,
    )
