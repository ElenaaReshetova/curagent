"""Deterministic structural and compliance validation for artifacts."""

from __future__ import annotations

import hashlib
import re
from typing import Optional

from src.orchestrator.models import (
    ArtifactDraft,
    ArtifactType,
    ComplianceReport,
    ComplianceViolation,
    NormalizedTaskSpec,
    VerificationFinding,
    VerificationReport,
    VerificationStatus,
)

# Required section markers per artifact type (case-insensitive)
_REQUIRED_SECTIONS: dict[ArtifactType, list[str]] = {
    ArtifactType.BUSINESS_REQUIREMENTS: [
        "problem", "goal", "user stor", "requirement",
        "проблем", "цел", "пользовател", "требован", "user story",
    ],
    ArtifactType.SYSTEM_REQUIREMENTS: [
        "requirement", "scope", "non-functional", "nfr",
    ],
    ArtifactType.TEST_CASE_PACK: [
        "test case", "precondition", "step", "expected",
    ],
    ArtifactType.CODE_ANALYSIS: [
        "finding", "summary", "recommend",
    ],
}

_SECRET_PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),  # AWS key
    re.compile(r"xox[baprs]-[0-9a-zA-Z-]{10,}"),  # Slack token
    re.compile(r"(?i)(api[_-]?key|secret|password)\s*[:=]\s*\S{8,}"),
]

_PII_PATTERNS = [
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),  # SSN-like
    re.compile(r"\b\d{16}\b"),  # card-like
    # Real-looking emails; ignore common placeholders
    re.compile(
        r"(?i)\b(?![\w.+-]+@(?:example\.com|example\.org|test\.local|localhost)\b)"
        r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"
    ),
    re.compile(r"(?:\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}"),  # RU phone
    re.compile(r"(?i)\b(?:паспорт|passport)\b.{0,20}\b\d{4}\s?\d{6}\b"),  # RU passport
    re.compile(r"(?i)\b(?:инн)\b.{0,10}\b\d{10,12}\b"),  # INN
    re.compile(r"(?i)\b(?:снилс)\b.{0,10}\b\d{3}[-\s]?\d{3}[-\s]?\d{3}[-\s]?\d{2}\b"),  # SNILS
]


def checksum(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def validate_structure(artifact: ArtifactDraft) -> list[VerificationFinding]:
    """Deterministic structural checks before semantic verification."""
    findings: list[VerificationFinding] = []
    content = artifact.content
    lower = content.lower()

    if len(content.strip()) < 200:
        findings.append(VerificationFinding(
            section="global",
            severity="blocking",
            message="Artifact too short (< 200 chars). Likely incomplete.",
        ))

    required = _REQUIRED_SECTIONS.get(artifact.type, [])
    if required:
        matched = sum(1 for sec in required if sec in lower)
        if matched < max(1, len(required) // 4):
            findings.append(VerificationFinding(
                section="structure",
                severity="blocking",
                message=f"Missing required sections for {artifact.type.value}. "
                        f"Expected markers: {required}",
            ))

    if artifact.type == ArtifactType.TEST_CASE_PACK:
        if not re.search(r"(?i)(test case|tc-\d|тест.?кейс)", content):
            findings.append(VerificationFinding(
                section="test_cases",
                severity="blocking",
                message="No identifiable test cases found.",
            ))

    return findings


def run_compliance_checks(artifact: ArtifactDraft) -> ComplianceReport:
    """Deterministic compliance: secrets, PII patterns."""
    violations: list[ComplianceViolation] = []
    content = artifact.content

    for i, pat in enumerate(_SECRET_PATTERNS):
        if pat.search(content):
            violations.append(ComplianceViolation(
                rule_id=f"secret_pattern_{i}",
                severity="blocking",
                message="Potential secret/credential detected in artifact content.",
            ))

    for i, pat in enumerate(_PII_PATTERNS):
        if pat.search(content):
            violations.append(ComplianceViolation(
                rule_id=f"pii_pattern_{i}",
                severity="blocking",
                message="Potential PII detected in artifact content.",
            ))

    blocking = [v for v in violations if v.severity == "blocking"]
    status = VerificationStatus.FAIL if blocking else VerificationStatus.PASS
    return ComplianceReport(artifact_id=artifact.artifact_id, status=status, violations=violations)


def merge_structural_into_report(
    artifact: ArtifactDraft,
    structural_findings: list[VerificationFinding],
    semantic_status: VerificationStatus,
    semantic_findings: list[VerificationFinding],
    scores: dict[str, float],
    required_fixes: list[str],
) -> VerificationReport:
    """Combine structural + semantic verification results."""
    all_findings = structural_findings + semantic_findings
    blocking = [f for f in all_findings if f.severity == "blocking"]

    if blocking:
        status = VerificationStatus.REWORK
    elif semantic_status == VerificationStatus.FAIL:
        status = VerificationStatus.FAIL
    elif semantic_status == VerificationStatus.REWORK:
        status = VerificationStatus.REWORK
    else:
        status = VerificationStatus.PASS

    return VerificationReport(
        artifact_id=artifact.artifact_id,
        artifact_version=artifact.version,
        status=status,
        scores=scores,
        findings=all_findings,
        required_fixes=required_fixes,
    )
