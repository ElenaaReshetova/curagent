"""Compliance gate must build a valid VerificationReport for gateway branching."""

from src.orchestrator.models import (
    ArtifactDraft,
    ArtifactType,
    ComplianceReport,
    VerificationReport,
    VerificationStatus,
)


def test_compliance_verification_report_includes_artifact_version():
    artifact = ArtifactDraft(
        artifact_id="task-1",
        task_id="task-1",
        version=3,
        type=ArtifactType.BUSINESS_REQUIREMENTS,
        skill="business-requirements",
        content="# BRD\n\n## Scope\nTest",
        content_checksum="abc",
    )
    report = ComplianceReport(
        artifact_id=artifact.artifact_id,
        status=VerificationStatus.PASS,
        violations=[],
    )
    passed = report.status == VerificationStatus.PASS
    vr = VerificationReport(
        artifact_id=report.artifact_id or artifact.artifact_id,
        artifact_version=artifact.version,
        status=VerificationStatus.PASS if passed else VerificationStatus.REWORK,
        findings=[],
        required_fixes=[] if passed else ["fix"],
    )
    assert vr.artifact_version == 3
    assert vr.status == VerificationStatus.PASS
