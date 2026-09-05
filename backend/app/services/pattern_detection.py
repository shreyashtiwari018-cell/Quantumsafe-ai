"""
QuantumSafe AI — Pattern Intelligence Engine

Detects recurring HSE safety patterns from saved reports.

Current approach:
    - Groups reports by hazard + location + failed barrier
    - Calculates recurrence and SIF ratio
    - Calculates a priority score
    - Classifies pattern severity
    - Generates an explanation
    - Generates a recommended HSE action
    - Keeps the existing API-compatible Pattern fields

Future upgrade:
    - NLP embeddings / semantic clustering once real report volume is large.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import List, Dict, Any


# ---------------------------------------------------------------------------
# Pattern model
# ---------------------------------------------------------------------------

@dataclass
class Pattern:
    hazard: str
    location: str
    failed_barrier: str

    report_count: int
    sif_count: int

    report_ids: List[str] = field(default_factory=list)

    risk: str = "MEDIUM"

    # New intelligence fields
    priority_score: int = 0
    recurrence: str = "RECURRING"
    explanation: str = ""
    recommended_action: str = ""

    # -----------------------------------------------------------------------
    # Existing API property
    # -----------------------------------------------------------------------
    @property
    def sif_ratio(self) -> float:
        if self.report_count == 0:
            return 0.0

        return self.sif_count / self.report_count

    # -----------------------------------------------------------------------
    # Human-readable SIF percentage
    # -----------------------------------------------------------------------
    @property
    def sif_percentage(self) -> int:
        return round(self.sif_ratio * 100)

    # -----------------------------------------------------------------------
    # Pattern priority
    # -----------------------------------------------------------------------
    def calculate_priority(self) -> int:
        """
        Priority combines:
            - SIF ratio
            - recurrence frequency
            - failed barrier
            - overall severity

        Score range: 0–100.
        """

        # SIF contribution: maximum 60 points
        sif_score = self.sif_ratio * 60

        # Frequency contribution: maximum 25 points
        frequency_score = min(self.report_count * 5, 25)

        # Barrier failure contribution: 15 points
        barrier_score = 15 if self.failed_barrier != "(none identified)" else 5

        score = round(
            sif_score +
            frequency_score +
            barrier_score
        )

        return min(score, 100)


# ---------------------------------------------------------------------------
# Text normalization
# ---------------------------------------------------------------------------

def clean_value(value: Any, default: str = "Unspecified") -> str:
    """
    Safely convert database values into clean display strings.
    """

    if value is None:
        return default

    value = str(value).strip()

    if not value:
        return default

    return value


# ---------------------------------------------------------------------------
# Barrier extraction
# ---------------------------------------------------------------------------

def extract_barriers(value: Any) -> List[str]:
    """
    Supports both:
        "Atmospheric Testing; Standby Person"

    and:

        ["Atmospheric Testing", "Standby Person"]
    """

    if not value:
        return []

    if isinstance(value, str):
        parts = value.split(";")
    elif isinstance(value, list):
        parts = value
    else:
        parts = [str(value)]

    barriers = []

    for barrier in parts:
        barrier = str(barrier).strip()

        if barrier and barrier not in barriers:
            barriers.append(barrier)

    return barriers


# ---------------------------------------------------------------------------
# Risk classification
# ---------------------------------------------------------------------------

def calculate_risk(
    sif_ratio: float,
    report_count: int,
    failed_barrier: str,
) -> str:
    """
    Determine pattern risk using both SIF ratio and recurrence.

    Critical:
        Very high SIF exposure OR repeated high-frequency SIF pattern.

    High:
        Significant SIF exposure.

    Medium:
        Moderate exposure.

    Low:
        Low SIF exposure.
    """

    # Strong recurring SIF pattern
    if sif_ratio >= 0.80 and report_count >= 3:
        return "CRITICAL"

    # Extremely concentrated SIF pattern
    if sif_ratio >= 0.90:
        return "CRITICAL"

    # High-risk recurring pattern
    if sif_ratio >= 0.60 and report_count >= 3:
        return "HIGH"

    if sif_ratio >= 0.30:
        return "MEDIUM"

    return "LOW"


# ---------------------------------------------------------------------------
# Recurrence classification
# ---------------------------------------------------------------------------

def calculate_recurrence(report_count: int) -> str:
    """
    Classify how strongly a pattern is repeating.
    """

    if report_count >= 7:
        return "PERSISTENT"

    if report_count >= 5:
        return "RECURRING"

    if report_count >= 3:
        return "EMERGING"

    return "SINGLE"


# ---------------------------------------------------------------------------
# Recommended HSE action
# ---------------------------------------------------------------------------

def get_recommended_action(
    hazard: str,
    failed_barrier: str,
    risk: str,
) -> str:
    """
    Generate a practical action for the HSE team.
    """

    barrier = failed_barrier.lower()
    hazard_lower = hazard.lower()

    if "atmospheric" in barrier:
        return (
            "Verify atmospheric testing before entry and require documented "
            "gas-test results before work begins."
        )

    if "standby" in barrier or "person" in barrier:
        return (
            "Ensure a trained standby person is assigned and continuously "
            "available during the activity."
        )

    if "fall" in barrier or "protection" in barrier:
        return (
            "Verify fall-protection controls, anchorage and work-at-height "
            "authorization before starting the task."
        )

    if "permit" in barrier:
        return (
            "Review permit-to-work compliance and require authorization "
            "before the activity begins."
        )

    if "ppe" in barrier:
        return (
            "Verify required PPE availability, condition and correct usage "
            "before work starts."
        )

    if "confined" in hazard_lower:
        return (
            "Review confined-space entry controls, atmospheric testing, "
            "standby arrangements and rescue readiness."
        )

    if "height" in hazard_lower:
        return (
            "Review work-at-height controls and verify fall protection "
            "before the task begins."
        )

    if risk == "CRITICAL":
        return (
            "Prioritize immediate qualified HSE review and verify critical "
            "controls before the activity continues."
        )

    if risk == "HIGH":
        return (
            "Conduct a targeted HSE review and strengthen the identified "
            "failed control."
        )

    return (
        "Monitor the recurring condition and verify the relevant control "
        "during the next HSE review."
    )


# ---------------------------------------------------------------------------
# Pattern explanation
# ---------------------------------------------------------------------------

def build_explanation(
    hazard: str,
    location: str,
    barrier: str,
    report_count: int,
    sif_count: int,
    risk: str,
) -> str:
    """
    Generate an explanation suitable for the dashboard.
    """

    ratio = round((sif_count / report_count) * 100) if report_count else 0

    return (
        f"{report_count} reports involve {hazard} at {location}, "
        f"with {barrier} identified as the failed barrier. "
        f"{sif_count} of these reports ({ratio}%) have SIF potential. "
        f"Pattern priority is {risk}."
    )


# ---------------------------------------------------------------------------
# Main detector
# ---------------------------------------------------------------------------

def detect_patterns(
    reports: List[Dict],
    min_reports: int = 3,
) -> List[Pattern]:
    """
    Detect recurring safety patterns.

    Grouping key:
        hazard + location + failed barrier

    A pattern is returned only when it occurs at least `min_reports` times.

    Parameters
    ----------
    reports:
        List of report dictionaries from SQLite.

    min_reports:
        Minimum number of reports required for a pattern.

    Returns
    -------
    List[Pattern]
        Patterns sorted by priority first, then SIF ratio and frequency.
    """

    groups: Dict[tuple, List[Dict]] = defaultdict(list)

    # -----------------------------------------------------------------------
    # Build groups
    # -----------------------------------------------------------------------

    for report in reports:

        hazard = clean_value(
            report.get("hazard"),
            "Unclassified"
        )

        location = clean_value(
            report.get("location"),
            "Unspecified"
        )

        barriers = extract_barriers(
            report.get("barrier_failure")
        )

        if not barriers:
            barriers = ["(none identified)"]

        # Ignore completely unclassified reports.
        # These should not create false recurring patterns.
        if (
            hazard.lower() == "unclassified"
            and location.lower() == "unspecified"
            and barriers == ["(none identified)"]
        ):
            continue

        for barrier in barriers:

            key = (
                hazard.lower(),
                location.lower(),
                barrier.lower(),
            )

            groups[key].append(report)

    # -----------------------------------------------------------------------
    # Generate patterns
    # -----------------------------------------------------------------------

    patterns: List[Pattern] = []

    for group_reports in groups.values():

        # Minimum recurrence requirement
        if len(group_reports) < min_reports:
            continue

        first_report = group_reports[0]

        hazard = clean_value(
            first_report.get("hazard"),
            "Unclassified"
        )

        location = clean_value(
            first_report.get("location"),
            "Unspecified"
        )

        # Retrieve the barrier from the grouping key by looking at the
        # reports' barrier values.
        barrier_candidates = []

        for report in group_reports:

            barriers = extract_barriers(
                report.get("barrier_failure")
            )

            if not barriers:
                barriers = ["(none identified)"]

            for barrier in barriers:
                if barrier.lower() not in [
                    x.lower() for x in barrier_candidates
                ]:
                    barrier_candidates.append(barrier)

        # A group should normally contain one barrier.
        failed_barrier = barrier_candidates[0] if barrier_candidates else "(none identified)"

        # ---------------------------------------------------------------
        # SIF count
        # ---------------------------------------------------------------

        sif_count = 0

        for report in group_reports:

            try:
                sif_value = int(
                    report.get("sif_potential", 0)
                )
            except (TypeError, ValueError):
                sif_value = 0

            if sif_value == 1:
                sif_count += 1

        report_count = len(group_reports)

        sif_ratio = (
            sif_count / report_count
            if report_count
            else 0
        )

        # ---------------------------------------------------------------
        # Risk
        # ---------------------------------------------------------------

        risk = calculate_risk(
            sif_ratio=sif_ratio,
            report_count=report_count,
            failed_barrier=failed_barrier,
        )

        # ---------------------------------------------------------------
        # Recurrence
        # ---------------------------------------------------------------

        recurrence = calculate_recurrence(
            report_count
        )

        # ---------------------------------------------------------------
        # Report IDs
        # ---------------------------------------------------------------

        report_ids = []

        for report in group_reports:

            report_id = clean_value(
                report.get("report_id"),
                ""
            )

            if report_id and report_id not in report_ids:
                report_ids.append(report_id)

        # ---------------------------------------------------------------
        # Create pattern
        # ---------------------------------------------------------------

        pattern = Pattern(
            hazard=hazard,
            location=location,
            failed_barrier=failed_barrier,
            report_count=report_count,
            sif_count=sif_count,
            report_ids=report_ids,
            risk=risk,
            recurrence=recurrence,
        )

        # ---------------------------------------------------------------
        # Intelligence
        # ---------------------------------------------------------------

        pattern.priority_score = pattern.calculate_priority()

        pattern.explanation = build_explanation(
            hazard=hazard,
            location=location,
            barrier=failed_barrier,
            report_count=report_count,
            sif_count=sif_count,
            risk=risk,
        )

        pattern.recommended_action = get_recommended_action(
            hazard=hazard,
            failed_barrier=failed_barrier,
            risk=risk,
        )

        patterns.append(pattern)

    # -----------------------------------------------------------------------
    # Sort
    # -----------------------------------------------------------------------

    patterns.sort(
        key=lambda p: (
            p.priority_score,
            p.sif_ratio,
            p.report_count,
        ),
        reverse=True,
    )

    return patterns