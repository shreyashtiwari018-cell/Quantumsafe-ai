"""
Module 3: Information Extraction (rule-based baseline).

Extracts structured safety entities from free-text reports using the
keyword lexicon in app.data.taxonomy. This is intentionally simple
(keyword/phrase matching) so it's reproducible and explainable for the
Phase 1 MVP. Swap-in point for spaCy/transformer NER later — keep the
function signature (text -> ExtractionResult) stable so downstream
services don't need to change.
"""
from dataclasses import dataclass, field
from typing import List, Optional
from app.data.taxonomy import HAZARD_LEXICON, BARRIERS


@dataclass
class ExtractionResult:
    text: str
    matched_hazards: List[str] = field(default_factory=list)  # ordered, strongest first
    primary_hazard: Optional[str] = None
    life_saving_rule: Optional[str] = None
    matched_keywords: List[str] = field(default_factory=list)


def extract(text: str) -> ExtractionResult:
    lowered = text.lower()
    scores = {}
    hit_keywords = {}

    for hazard_key, info in HAZARD_LEXICON.items():
        hits = [kw for kw in info["keywords"] if kw in lowered]
        if hits:
            # Longer/more specific keyword matches score higher
            scores[hazard_key] = sum(len(k.split()) for k in hits) + len(hits)
            hit_keywords[hazard_key] = hits

    if not scores:
        return ExtractionResult(text=text)

    ordered = sorted(scores.keys(), key=lambda k: scores[k], reverse=True)
    primary = ordered[0]
    all_hits = []
    for h in ordered:
        all_hits.extend(hit_keywords[h])

    return ExtractionResult(
        text=text,
        matched_hazards=ordered,
        primary_hazard=primary,
        life_saving_rule=HAZARD_LEXICON[primary]["life_saving_rule"],
        matched_keywords=all_hits,
    )


def detect_barrier_failures(text: str, primary_hazard: Optional[str]) -> List[str]:
    """Returns list of barrier names that appear to have failed, based on
    failure-phrase matching for the given hazard category."""
    if not primary_hazard or primary_hazard not in BARRIERS:
        return []
    lowered = text.lower()
    failed = []
    for entry in BARRIERS[primary_hazard]:
        if any(phrase in lowered for phrase in entry["failure_keywords"]):
            failed.append(entry["barrier"])
    return failed
