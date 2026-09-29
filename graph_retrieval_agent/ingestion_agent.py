from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List

from openai import OpenAI
from pydantic import BaseModel, Field

from .config import settings
from .graph_db import graph_db
from .graph_schema import ALLOWED_TRIPLES, LAYER_BY_LABEL, RELATIONSHIP_RULES


class ExtractedEntity(BaseModel):
    ref: str
    label: str
    name: str
    properties: Dict[str, Any] = Field(default_factory=dict)


class ExtractedRelationship(BaseModel):
    source_ref: str
    relationship_type: str
    target_ref: str
    properties: Dict[str, Any] = Field(default_factory=dict)


class ExtractedGraph(BaseModel):
    entities: List[ExtractedEntity]
    relationships: List[ExtractedRelationship]


class NormalizedEntity(BaseModel):
    id: str
    label: str
    name: str
    layer: str
    properties: Dict[str, Any] = Field(default_factory=dict)


class NormalizedRelationship(BaseModel):
    source_id: str
    relationship_type: str
    target_id: str
    properties: Dict[str, Any] = Field(default_factory=dict)


class NormalizedGraph(BaseModel):
    source_name: str
    entities: List[NormalizedEntity]
    relationships: List[NormalizedRelationship]
    validation_warnings: List[str] = Field(default_factory=list)


class IngestionAgent:
    """Convert semi-structured source information into a validated L0-L4 graph."""

    def __init__(self) -> None:
        self.client = OpenAI(api_key=settings.openai_api_key)

    @staticmethod
    def _canonical_id(label: str, name: str) -> str:
        """Fallback ID when the legacy POC has no stronger natural key."""
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        digest = hashlib.sha1(f"{label}:{name}".encode("utf-8")).hexdigest()[:10]
        return f"{label.lower()}:{slug[:60]}:{digest}"

    @staticmethod
    def _neo4j_properties(properties: Dict[str, Any]) -> Dict[str, Any]:
        """Neo4j properties cannot contain nested maps; serialize complex values."""
        cleaned: Dict[str, Any] = {}
        for key, value in properties.items():
            if value is None or value == "":
                continue
            if isinstance(value, (str, int, float, bool)):
                cleaned[key] = value
            elif isinstance(value, list) and all(
                isinstance(item, (str, int, float, bool)) for item in value
            ):
                cleaned[key] = value
            else:
                cleaned[key] = json.dumps(value, ensure_ascii=True, sort_keys=True)
        return cleaned

    @staticmethod
    def _normalize_entity_properties(
        label: str,
        properties: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Map common LLM/source aliases to stable graph property names."""
        normalized = dict(properties or {})

        if label == "API":
            if normalized.get("method"):
                normalized["method"] = str(normalized["method"]).upper().strip()

        if label == "TestDataRequirement":
            if "fields" not in normalized and "requirements" in normalized:
                normalized["fields"] = normalized.pop("requirements")

        if label == "AutomationTest":
            if "script_reference" not in normalized and "script_location" in normalized:
                normalized["script_reference"] = normalized["script_location"]

        return normalized

    def _contextual_ids(
        self,
        refs: Dict[str, ExtractedEntity],
        relationships: List[ExtractedRelationship],
    ) -> Dict[str, str]:
        """
        Reuse the existing POC natural keys where possible so the upgrade enriches
        current nodes instead of creating a parallel duplicate graph.
        """
        process_for_step: Dict[str, str] = {}
        step_for_service: Dict[str, str] = {}
        service_for_api: Dict[str, str] = {}
        api_for_testdata: Dict[str, str] = {}
        api_for_automation: Dict[str, str] = {}

        for rel in relationships:
            if rel.relationship_type == "HAS_STEP":
                process_for_step[rel.target_ref] = rel.source_ref
            elif rel.relationship_type == "SUPPORTED_BY":
                step_for_service.setdefault(rel.target_ref, rel.source_ref)
            elif rel.relationship_type == "EXPOSES":
                service_for_api[rel.target_ref] = rel.source_ref
            elif rel.relationship_type == "REQUIRES_TEST_DATA":
                api_for_testdata[rel.target_ref] = rel.source_ref
            elif rel.relationship_type == "VALIDATED_BY":
                api_for_automation[rel.target_ref] = rel.source_ref

        ids: Dict[str, str] = {}

        # Natural-key labels from the existing POC.
        for ref, entity in refs.items():
            if entity.label in {"BusinessProcess", "Service"}:
                ids[ref] = entity.name.strip()
            elif entity.label in {"StrategicGoal", "Obligation"}:
                ids[ref] = self._canonical_id(entity.label, entity.name.strip())

        # ProcessStep legacy key: <process>:<step_no>.
        for ref, entity in refs.items():
            if entity.label != "ProcessStep":
                continue
            process_ref = process_for_step.get(ref)
            step_no = entity.properties.get("step_no")
            if process_ref and step_no is not None:
                ids[ref] = f"{refs[process_ref].name.strip()}:{int(step_no)}"
            else:
                ids[ref] = self._canonical_id(entity.label, entity.name.strip())

        # API legacy key: <service>:<METHOD>:<path>.
        for ref, entity in refs.items():
            if entity.label != "API":
                continue
            service_ref = service_for_api.get(ref)
            method = str(entity.properties.get("method", "")).upper().strip()
            path = str(entity.properties.get("path", "")).strip()
            if service_ref and method and path:
                ids[ref] = f"{refs[service_ref].name.strip()}:{method}:{path}"
            else:
                ids[ref] = self._canonical_id(entity.label, entity.name.strip())

        # Environment is a shared L4 context node (for example UAT).
        # Service-specific values such as base_url belong on DEPLOYED_TO, not
        # on the Environment node itself. This avoids creating/using an
        # environment ID that is accidentally tied to the first service.
        for ref, entity in refs.items():
            if entity.label != "Environment":
                continue
            slug = re.sub(r"[^a-z0-9]+", "-", entity.name.lower()).strip("-")
            ids[ref] = f"environment:{slug}"

        # Test data legacy key: <process-step-id>:testdata when the path can be traced.
        for ref, entity in refs.items():
            if entity.label != "TestDataRequirement":
                continue
            api_ref = api_for_testdata.get(ref)
            service_ref = service_for_api.get(api_ref) if api_ref else None
            step_ref = step_for_service.get(service_ref) if service_ref else None
            if step_ref and step_ref in ids:
                ids[ref] = f"{ids[step_ref]}:testdata"
            elif api_ref and api_ref in ids:
                ids[ref] = f"{ids[api_ref]}:testdata"
            else:
                ids[ref] = self._canonical_id(entity.label, entity.name.strip())

        # Automation legacy key: <api-id>:automation.
        for ref, entity in refs.items():
            if entity.label != "AutomationTest":
                continue
            api_ref = api_for_automation.get(ref)
            if api_ref and api_ref in ids:
                ids[ref] = f"{ids[api_ref]}:automation"
            else:
                ids[ref] = self._canonical_id(entity.label, entity.name.strip())

        for ref, entity in refs.items():
            ids.setdefault(ref, self._canonical_id(entity.label, entity.name.strip()))

        return ids

    @staticmethod
    def _clean_json(text: str) -> str:
        text = text.strip()
        if text.startswith("```"):
            text = text.replace("```json", "", 1)
            text = text.replace("```", "")
        return text.strip()

    def _extract_with_llm(self, source_text: str, source_name: str) -> ExtractedGraph:
        relationship_rules = [
            f"{r.source_label} -[{r.relationship_type}]-> {r.target_label}"
            for r in RELATIONSHIP_RULES
        ]

        prompt = f"""
You are the Ingestion Agent for a Graph Retrieval Agent.

Your job is to convert the source below into graph-ready entities and relationships.
The source may be semi-structured and is NOT guaranteed to be pre-classified into columns.

Use only these node labels and layers:
{json.dumps(LAYER_BY_LABEL, indent=2)}

Use only these relationship patterns:
{json.dumps(relationship_rules, indent=2)}

Important rules:
- Extract only facts supported by the source. Do not invent missing services, APIs, environments, test data, automation, obligations, or goals.
- Use ProcessStep for explicitly described steps within a BusinessProcess.
- Use API only when an endpoint/method/operation is explicitly present.
- Use DEPENDS_ON only when a service dependency is explicitly stated.
- Keep entity metadata inside entity properties using these canonical keys when applicable:
  ProcessStep.step_no, Service.service_type, API.method, API.path,
  TestDataRequirement.fields, AutomationTest.test_type, AutomationTest.script_reference,
  AutomationTest.execution_command and AutomationTest.automation_tag.
- Put relationship-specific metadata on the relationship when appropriate. Examples:
  HAS_STEP.sequence, DEPENDS_ON.dependency_type/criticality, DEPLOYED_TO.base_url/version/active.
- For ProcessStep, always include step_no in entity properties when the source gives the sequence.
- For API, always include method and path in entity properties when present.
- Use short stable temporary refs such as goal_1, obligation_1, process_1, step_1, service_1.
- Every relationship source_ref and target_ref must match an entity ref.
- Return JSON only. No markdown.

Return exactly this structure:
{{
  "entities": [
    {{
      "ref": "process_1",
      "label": "BusinessProcess",
      "name": "Customer Onboarding",
      "properties": {{}}
    }}
  ],
  "relationships": [
    {{
      "source_ref": "process_1",
      "relationship_type": "HAS_STEP",
      "target_ref": "step_1",
      "properties": {{}}
    }}
  ]
}}

Source name: {source_name}

Source:
---
{source_text}
---
"""

        response = self.client.responses.create(
            model=settings.openai_model,
            input=prompt,
            max_output_tokens=4000,
        )
        payload = json.loads(self._clean_json(response.output_text))
        return ExtractedGraph.model_validate(payload)

    def _normalize_and_validate(
        self,
        extracted: ExtractedGraph,
        source_name: str,
    ) -> NormalizedGraph:
        refs: Dict[str, ExtractedEntity] = {}
        for entity in extracted.entities:
            if entity.ref in refs:
                raise ValueError(f"Duplicate entity ref: {entity.ref}")
            if entity.label not in LAYER_BY_LABEL:
                raise ValueError(f"Unsupported entity label: {entity.label}")
            if not entity.name.strip():
                raise ValueError(f"Entity {entity.ref} has an empty name")
            refs[entity.ref] = entity

        canonical_by_ref = self._contextual_ids(refs, extracted.relationships)
        normalized_entities_by_id: Dict[str, NormalizedEntity] = {}

        for ref, entity in refs.items():
            entity_id = canonical_by_ref[ref]
            properties = self._normalize_entity_properties(
                entity.label,
                entity.properties,
            )
            properties = self._neo4j_properties(properties)
            properties["source_name"] = source_name

            existing = normalized_entities_by_id.get(entity_id)
            if existing:
                existing.properties.update(properties)
            else:
                normalized_entities_by_id[entity_id] = NormalizedEntity(
                    id=entity_id,
                    label=entity.label,
                    name=entity.name.strip(),
                    layer=LAYER_BY_LABEL[entity.label],
                    properties=properties,
                )

        normalized_relationships: List[NormalizedRelationship] = []
        seen_relationships = set()

        for relationship in extracted.relationships:
            if relationship.source_ref not in refs:
                raise ValueError(
                    f"Unknown relationship source_ref: {relationship.source_ref}"
                )
            if relationship.target_ref not in refs:
                raise ValueError(
                    f"Unknown relationship target_ref: {relationship.target_ref}"
                )

            source = refs[relationship.source_ref]
            target = refs[relationship.target_ref]
            triple = (
                source.label,
                relationship.relationship_type,
                target.label,
            )
            if triple not in ALLOWED_TRIPLES:
                raise ValueError(
                    "Invalid relationship for graph schema: "
                    f"{source.label} -[{relationship.relationship_type}]-> {target.label}"
                )

            source_id = canonical_by_ref[relationship.source_ref]
            target_id = canonical_by_ref[relationship.target_ref]
            dedupe_key = (source_id, relationship.relationship_type, target_id)
            if dedupe_key in seen_relationships:
                continue
            seen_relationships.add(dedupe_key)

            normalized_relationships.append(
                NormalizedRelationship(
                    source_id=source_id,
                    relationship_type=relationship.relationship_type,
                    target_id=target_id,
                    properties=self._neo4j_properties(relationship.properties),
                )
            )

        layers_present = {
            entity.layer for entity in normalized_entities_by_id.values()
        }
        warnings = [
            f"No {layer} entity was extracted from this source."
            for layer in ("L0", "L1", "L2", "L3", "L4")
            if layer not in layers_present
        ]

        return NormalizedGraph(
            source_name=source_name,
            entities=list(normalized_entities_by_id.values()),
            relationships=normalized_relationships,
            validation_warnings=warnings,
        )

    def preview(self, source_text: str, source_name: str = "inline") -> NormalizedGraph:
        if not source_text.strip():
            raise ValueError("Source text is empty")
        extracted = self._extract_with_llm(source_text, source_name)
        return self._normalize_and_validate(extracted, source_name)

    def preview_file(self, path: str | Path) -> NormalizedGraph:
        path = Path(path)
        return self.preview(path.read_text(encoding="utf-8"), path.name)

    @staticmethod
    def _create_constraints() -> None:
        for label in LAYER_BY_LABEL:
            graph_db.run(
                f"""
                CREATE CONSTRAINT {label.lower()}_id IF NOT EXISTS
                FOR (n:{label})
                REQUIRE n.id IS UNIQUE
                """
            )

    @staticmethod
    def _upsert_graph(graph: NormalizedGraph) -> Dict[str, Any]:
        IngestionAgent._create_constraints()

        for entity in graph.entities:
            # BusinessProcess and Service already have unique-name constraints in the
            # original POC, so match them by name and enrich with the new id/layer.
            if entity.label in {"BusinessProcess", "Service"}:
                merge_key = "name"
                merge_value = entity.name
            else:
                merge_key = "id"
                merge_value = entity.id

            graph_db.run(
                f"""
                MERGE (n:{entity.label} {{{merge_key}: $merge_value}})
                SET n.id = $id,
                    n.name = $name,
                    n.layer = $layer
                SET n += $properties
                """,
                {
                    "merge_value": merge_value,
                    "id": entity.id,
                    "name": entity.name,
                    "layer": entity.layer,
                    "properties": entity.properties,
                },
            )

        entity_by_id = {entity.id: entity for entity in graph.entities}
        process_contexts = sorted(
            {
                entity.name
                for entity in graph.entities
                if entity.label == "BusinessProcess"
            }
        )

        for relationship in graph.relationships:
            source = entity_by_id[relationship.source_id]
            target = entity_by_id[relationship.target_id]
            # labels/type are safe because the normalized graph passed schema validation.
            # process_contexts is relationship provenance used by retrieval to keep
            # shared Service nodes from leaking context across business processes.
            graph_db.run(
                f"""
                MATCH (source:{source.label} {{id: $source_id}})
                MATCH (target:{target.label} {{id: $target_id}})
                MERGE (source)-[r:{relationship.relationship_type}]->(target)
                SET r += $properties
                SET r.process_contexts = reduce(
                    acc = coalesce(r.process_contexts, []),
                    value IN $process_contexts |
                    CASE
                        WHEN value IN acc THEN acc
                        ELSE acc + value
                    END
                )
                SET r.source_names = reduce(
                    acc = coalesce(r.source_names, []),
                    value IN [$source_name] |
                    CASE
                        WHEN value IN acc THEN acc
                        ELSE acc + value
                    END
                )
                """,
                {
                    "source_id": relationship.source_id,
                    "target_id": relationship.target_id,
                    "properties": relationship.properties,
                    "process_contexts": process_contexts,
                    "source_name": graph.source_name,
                },
            )

        return {
            "status": "success",
            "source_name": graph.source_name,
            "nodes_upserted": len(graph.entities),
            "relationships_upserted": len(graph.relationships),
            "validation_warnings": graph.validation_warnings,
        }

    def ingest(self, source_text: str, source_name: str = "inline") -> Dict[str, Any]:
        normalized = self.preview(source_text, source_name)
        result = self._upsert_graph(normalized)
        result["normalized_graph"] = normalized.model_dump()
        return result

    def ingest_file(self, path: str | Path) -> Dict[str, Any]:
        path = Path(path)
        return self.ingest(path.read_text(encoding="utf-8"), path.name)


ingestion_agent = IngestionAgent()
