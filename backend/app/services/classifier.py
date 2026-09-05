"""
Module 4: SIF Classification — inference wrapper.

Loads the trained TF-IDF+LogisticRegression model if available. If the
model file is missing (e.g. training hasn't been run yet, or a demo
machine doesn't have it), falls back to a rule-based heuristic so the
system still produces a usable result. Per spec rule #11: "Make the
system work even if the advanced ML model is unavailable."
"""
import os
from dataclasses import dataclass
from typing import Optional

MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "models", "sif_classifier.joblib")

_model = None
_model_load_attempted = False


@dataclass
class ClassificationResult:
    sif_potential: bool
    confidence: float
    method: str  # "ml_model" or "rule_based_fallback"


def _try_load_model():
    global _model, _model_load_attempted
    if _model_load_attempted:
        return
    _model_load_attempted = True
    try:
        import joblib
        if os.path.exists(MODEL_PATH):
            _model = joblib.load(MODEL_PATH)
    except Exception:
        _model = None


def classify(text: str, matched_hazards, failed_barriers) -> ClassificationResult:
    _try_load_model()

    if _model is not None:
        proba = _model.predict_proba([text])[0]
        classes = list(_model.classes_)
        idx_1 = classes.index(1) if 1 in classes else classes.index(True)
        confidence = float(proba[idx_1])
        return ClassificationResult(
            sif_potential=confidence >= 0.5,
            confidence=confidence,
            method="ml_model",
        )

    # --- Rule-based fallback ---
    # Heuristic: SIF-potential if a recognized hazard matched AND at least
    # one barrier failure phrase was found. Confidence is a simple proxy,
    # not a calibrated probability.
    has_hazard = len(matched_hazards) > 0
    has_barrier_failure = len(failed_barriers) > 0
    sif = has_hazard and has_barrier_failure
    if sif:
        confidence = 0.75 + min(0.2, 0.05 * len(failed_barriers))
    elif has_hazard:
        confidence = 0.4
    else:
        confidence = 0.15
    return ClassificationResult(
        sif_potential=sif,
        confidence=round(min(confidence, 0.99), 3),
        method="rule_based_fallback",
    )
