"""Seed catalog for artifact contracts and interface I/O mappings."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid5

from src.platform.contracts.models import ArtifactContract

NS = UUID("8f1c2a90-4e6d-4b7a-9c3e-1d5f8a2b04ef")

# interface_key -> (input_contract_key, output_contract_key)
INTERFACE_CONTRACTS: dict[str, tuple[str, str]] = {
    "analysis.problem.understand@1": ("WorkItem@1", "ProblemUnderstandingPatch@1"),
    "analysis.business_requirements.generate@1": ("WorkItem@1", "BusinessRequirementsArtifact@1"),
    "analysis.system_requirements.generate@1": (
        "ProblemUnderstandingArtifact@1",
        "SystemRequirementsPatch@1",
    ),
    "analysis.code_analysis.generate@1": ("Artifact@1", "ArtifactPatch@1"),
    "analysis.requirements.validate@2": ("RequirementsArtifact@1", "QualityReviewPatch@1"),
    "analysis.requirements.improve@1": ("RequirementsArtifact@1", "ArtifactPatch@1"),
    "routing.classify@1": ("WorkItem@1", "RoutingDecision@1"),
    "artifact.render@1": ("Artifact@1", "Artifact@1"),
}


def _id(key: str) -> UUID:
    return uuid5(NS, f"artifact-contract:{key}")


def _object_schema(*required: str) -> dict:
    schema: dict = {"type": "object", "additionalProperties": True}
    if required:
        schema["required"] = list(required)
    return schema


def build_artifact_contracts() -> list[ArtifactContract]:
    now = datetime.utcnow()
    specs: list[tuple[str, str, str, str, list[str], list[str]]] = [
        (
            "WorkItem@1",
            "Work Item",
            "work_item",
            "Normalized task or request from ingress (Jira, Slack, manual).",
            [],
            ["SlackWorkItem@1", "CanonicalWorkItem@1"],
        ),
        (
            "SlackWorkItem@1",
            "Slack Work Item",
            "work_item",
            "Work item sourced from a Slack thread.",
            ["WorkItem@1"],
            [],
        ),
        (
            "CanonicalWorkItem@1",
            "Canonical Work Item",
            "work_item",
            "Platform-normalized work item envelope.",
            ["WorkItem@1"],
            [],
        ),
        (
            "ProblemUnderstandingArtifact@1",
            "Problem Understanding",
            "artifact",
            "Scoped problem statement with actors, constraints and open questions.",
            [],
            ["ProblemUnderstandingPatch@1"],
        ),
        (
            "ProblemUnderstandingPatch@1",
            "Problem Understanding Patch",
            "patch",
            "Patch updating the problem understanding artifact.",
            ["ProblemUnderstandingArtifact@1"],
            [],
        ),
        (
            "BusinessRequirementsArtifact@1",
            "Business Requirements",
            "artifact",
            "BRD / PRD with goals, user stories and acceptance criteria.",
            [],
            ["ArtifactPatch@1"],
        ),
        (
            "SystemRequirementsArtifact@1",
            "System Requirements",
            "artifact",
            "System requirements document (v1).",
            [],
            ["SystemRequirementsPatch@1", "ArtifactPatch@1"],
        ),
        (
            "SystemRequirementsArtifact@2",
            "System Requirements",
            "artifact",
            "System requirements document (v2).",
            [],
            ["SystemRequirementsPatch@1", "ArtifactPatch@1"],
        ),
        (
            "SystemRequirementsPatch@1",
            "System Requirements Patch",
            "patch",
            "Patch updating system requirements.",
            ["SystemRequirementsArtifact@1", "SystemRequirementsArtifact@2"],
            [],
        ),
        (
            "RequirementsArtifact@1",
            "Requirements",
            "artifact",
            "Generic requirements artifact for review and validation skills.",
            [],
            ["QualityReviewPatch@1", "ArtifactPatch@1"],
        ),
        (
            "QualityReviewPatch@1",
            "Quality Review Patch",
            "patch",
            "Findings from a requirements quality review.",
            ["RequirementsArtifact@1"],
            [],
        ),
        (
            "RoutingDecision@1",
            "Routing Decision",
            "decision",
            "Classifier output selecting the next playbook or flow.",
            [],
            [],
        ),
        (
            "Artifact@1",
            "Generic Artifact",
            "artifact",
            "Fallback typed artifact for skills without a specific schema.",
            [],
            ["ArtifactPatch@1"],
        ),
        (
            "ArtifactPatch@1",
            "Generic Artifact Patch",
            "patch",
            "Fallback patch envelope for skill output.",
            ["Artifact@1"],
            [],
        ),
    ]
    contracts: list[ArtifactContract] = []
    for key, name, kind, description, satisfies, accepts in specs:
        base_name = key.rsplit("@", 1)[0]
        required = ["type"] if kind != "work_item" else ["title"]
        contracts.append(
            ArtifactContract(
                id=_id(key),
                key=key,
                name=name,
                description=description,
                kind=kind,  # type: ignore[arg-type]
                json_schema=_object_schema(*required),
                satisfies=satisfies,
                accepts=accepts,
                status="active",
                updated_at=now,
            )
        )
    return contracts


def default_interface_contracts(interface_key: str) -> tuple[str, str]:
    return INTERFACE_CONTRACTS.get(interface_key, ("Artifact@1", "ArtifactPatch@1"))
