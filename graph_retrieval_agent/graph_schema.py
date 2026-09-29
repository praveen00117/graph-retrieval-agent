from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple


# Canonical L0-L4 mapping agreed for the current Graph Retrieval Agent MVP.
LAYER_BY_LABEL: Dict[str, str] = {
    "StrategicGoal": "L0",
    "Obligation": "L1",
    "BusinessProcess": "L2",
    "ProcessStep": "L2",
    "Service": "L3",
    "API": "L3",
    "Environment": "L4",
    "TestDataRequirement": "L4",
    "AutomationTest": "L4",
}


@dataclass(frozen=True)
class RelationshipRule:
    source_label: str
    relationship_type: str
    target_label: str


RELATIONSHIP_RULES: Tuple[RelationshipRule, ...] = (
    RelationshipRule("StrategicGoal", "DRIVES", "Obligation"),
    RelationshipRule("Obligation", "FULFILLED_BY", "BusinessProcess"),
    RelationshipRule("BusinessProcess", "HAS_STEP", "ProcessStep"),
    RelationshipRule("ProcessStep", "NEXT_STEP", "ProcessStep"),
    RelationshipRule("ProcessStep", "SUPPORTED_BY", "Service"),
    RelationshipRule("Service", "EXPOSES", "API"),
    RelationshipRule("Service", "DEPENDS_ON", "Service"),
    RelationshipRule("Service", "DEPLOYED_TO", "Environment"),
    RelationshipRule("API", "REQUIRES_TEST_DATA", "TestDataRequirement"),
    RelationshipRule("API", "VALIDATED_BY", "AutomationTest"),
)

ALLOWED_RELATIONSHIP_TYPES = {
    rule.relationship_type for rule in RELATIONSHIP_RULES
}

ALLOWED_TRIPLES = {
    (rule.source_label, rule.relationship_type, rule.target_label)
    for rule in RELATIONSHIP_RULES
}
