"""
Configurable taxonomy for QuantumSafe AI.

This file is the single source of truth for:
- Hazard categories
- IOGP Life-Saving Rules
- Barrier types and their typical failure phrasing
- Keyword lexicons used by the rule-based extraction layer (Phase 1 baseline)

Per project spec: this taxonomy must be configurable, not hard-coded into
business logic. All services import FROM here rather than defining their
own literals, so adding a new hazard/rule/barrier means editing ONLY this
file.
"""

# ---------------------------------------------------------------------------
# IOGP Life-Saving Rules (12 standard rules; extend as needed)
# ---------------------------------------------------------------------------
LIFE_SAVING_RULES = [
    "Working at Height",
    "Confined Space",
    "Energy Isolation",
    "Hot Work",
    "Line of Fire",
    "Driving",
    "Lifting Operations",
    "Electrical",
    "Fire / Explosion",
    "Chemical Exposure",
    "Permit to Work",
    "Management of Change",
]

# ---------------------------------------------------------------------------
# Hazard categories -> keyword lexicon used for rule-based matching.
# Order matters slightly (first strong match wins for "primary" hazard),
# so keep more specific hazards above generic ones.
# ---------------------------------------------------------------------------
HAZARD_LEXICON = {
    "CONFINED_SPACE": {
        "keywords": ["confined space", "vessel entry", "tank entry", "manhole",
                     "atmospheric testing", "gas testing", "standby person"],
        "life_saving_rule": "Confined Space",
        "severity": 9,
    },
    "WORKING_AT_HEIGHT": {
        "keywords": ["working at height", "fall protection", "harness", "scaffold",
                      "ladder", "elevated platform", "fall from height", "guardrail"],
        "life_saving_rule": "Working at Height",
        "severity": 9,
    },
    "ENERGY_ISOLATION": {
        "keywords": ["loto", "lockout", "tagout", "energy isolation", "isolation not performed",
                      "stored energy", "de-energized", "energized equipment"],
        "life_saving_rule": "Energy Isolation",
        "severity": 9,
    },
    "HOT_WORK": {
        "keywords": ["hot work", "welding", "grinding", "cutting torch", "spark",
                     "fire watch", "flammable atmosphere"],
        "life_saving_rule": "Hot Work",
        "severity": 8,
    },
    "LINE_OF_FIRE": {
        "keywords": ["line of fire", "dropped object", "suspended load", "pinch point",
                     "struck by", "moving machinery"],
        "life_saving_rule": "Line of Fire",
        "severity": 7,
    },
    "VEHICLE": {
        "keywords": ["vehicle", "reversing", "pedestrian walkway", "spotter",
                     "forklift", "traffic", "speeding"],
        "life_saving_rule": "Driving",
        "severity": 7,
    },
    "LIFTING": {
        "keywords": ["crane", "lifting operation", "rigging", "sling", "load chart",
                     "hoist"],
        "life_saving_rule": "Lifting Operations",
        "severity": 8,
    },
    "ELECTRICAL": {
        "keywords": ["electrical", "live wire", "exposed cable", "shock hazard",
                     "electrocution", "panel open"],
        "life_saving_rule": "Electrical",
        "severity": 8,
    },
    "FIRE": {
        "keywords": ["fire", "explosion", "flammable", "gas leak", "ignition source"],
        "life_saving_rule": "Fire / Explosion",
        "severity": 9,
    },
    "CHEMICAL": {
        "keywords": ["chemical spill", "toxic", "hazardous material", "ppe not worn",
                     "respirator", "exposure to chemical"],
        "life_saving_rule": "Chemical Exposure",
        "severity": 7,
    },
    "PPE": {
        "keywords": ["ppe", "personal protective equipment", "safety glasses",
                     "gloves not worn", "helmet"],
        "life_saving_rule": "Permit to Work",
        "severity": 4,
    },
    "HOUSEKEEPING": {
        "keywords": ["housekeeping", "spill", "cluttered", "obstruction", "slip hazard",
                     "trip hazard", "oil spill"],
        "life_saving_rule": "Permit to Work",
        "severity": 3,
    },
}

# ---------------------------------------------------------------------------
# Barrier definitions: what control is supposed to prevent the hazard,
# and phrasing patterns that indicate the barrier failed or was absent.
# ---------------------------------------------------------------------------
BARRIERS = {
    "CONFINED_SPACE": [
        {"barrier": "Atmospheric Testing",
         "failure_keywords": ["without gas testing", "no gas test", "atmospheric testing not performed",
                               "without atmospheric testing"]},
        {"barrier": "Standby Person",
         "failure_keywords": ["no standby person", "standby person was not present", "without a standby"]},
    ],
    "WORKING_AT_HEIGHT": [
        {"barrier": "Fall Protection",
         "failure_keywords": ["without a safety harness", "without fall protection", "harness not used",
                               "no harness"]},
        {"barrier": "Scaffold Inspection",
         "failure_keywords": ["scaffold not inspected", "improper scaffolding", "unstable scaffold"]},
    ],
    "ENERGY_ISOLATION": [
        {"barrier": "Lockout/Tagout",
         "failure_keywords": ["isolation not performed", "without loto", "lock not applied",
                               "energized equipment"]},
    ],
    "HOT_WORK": [
        {"barrier": "Fire Watch",
         "failure_keywords": ["no fire watch", "without a fire watch permit", "hot work permit missing"]},
    ],
    "LINE_OF_FIRE": [
        {"barrier": "Exclusion Zone",
         "failure_keywords": ["no barricade", "exclusion zone not maintained", "workers under suspended load"]},
    ],
    "VEHICLE": [
        {"barrier": "Traffic Segregation / Spotter",
         "failure_keywords": ["without a spotter", "no spotter", "pedestrian path not separated",
                               "path not segregated"]},
    ],
    "LIFTING": [
        {"barrier": "Rigging Inspection",
         "failure_keywords": ["sling not inspected", "load chart not followed", "rigging failure"]},
    ],
    "ELECTRICAL": [
        {"barrier": "Insulation / De-energization",
         "failure_keywords": ["panel left open", "not de-energized", "exposed live wire"]},
    ],
    "FIRE": [
        {"barrier": "Ignition Control",
         "failure_keywords": ["ignition source present", "flammable material nearby"]},
    ],
    "CHEMICAL": [
        {"barrier": "PPE / Respiratory Protection",
         "failure_keywords": ["ppe not worn", "respirator not used", "without protective equipment"]},
    ],
    "PPE": [
        {"barrier": "PPE Compliance",
         "failure_keywords": ["not wearing", "ppe not worn", "without gloves", "without safety glasses"]},
    ],
    "HOUSEKEEPING": [
        {"barrier": "Housekeeping / Barricading",
         "failure_keywords": ["not barricaded", "left uncleaned", "obstruction not removed"]},
    ],
}

RISK_LEVELS = [
    (0, 30, "LOW"),
    (31, 60, "MEDIUM"),
    (61, 80, "HIGH"),
    (81, 100, "CRITICAL"),
]

REPORT_TYPES = ["UNSAFE_ACT", "UNSAFE_CONDITION", "NEAR_MISS", "INCIDENT"]
