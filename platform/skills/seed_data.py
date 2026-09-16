"""Shared seed builders for JSON and PostgreSQL skills stores."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid5

from src.platform.skills.models import (
    SkillBindingRef,
    SkillFile,
    SkillRecord,
    SkillTestCase,
    SkillVersion,
)
from src.platform.skills.validation import validate_version

NS = UUID("c3a91f0e-7b2d-4e5a-9c18-4f6d8a2b01ef")


def seed_id(kind: str, key: str) -> UUID:
    return uuid5(NS, f"{kind}:{key}")


def checksum(markdown: str, manifest: dict, files: list[SkillFile] | None = None) -> str:
    import hashlib
    import json

    payload = {
        "md": markdown,
        "manifest": manifest,
        "files": [
            {"path": f.path, "kind": f.kind, "content_text": f.content_text}
            for f in (files or [])
        ],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def interface_index() -> tuple[set[str], dict[str, list[str]]]:
    """Capability ceiling per interface.

    Prefer the platform store (what the Skills UI edits). Fall back to the
    governed catalog for missing keys / empty stores so seed builders still work.
    """
    keys: set[str] = set()
    caps: dict[str, list[str]] = {}

    try:
        from src.platform.store import list_skill_interfaces

        for iface in list_skill_interfaces():
            keys.add(iface.key)
            caps[iface.key] = list(iface.required_capabilities or [])
    except Exception:
        pass

    try:
        from src.platform.seed.governed_catalog import build_skill_interfaces

        for iface in build_skill_interfaces():
            if iface.key in caps:
                continue
            keys.add(iface.key)
            caps[iface.key] = list(iface.required_capabilities or [])
    except Exception:
        pass

    return keys, caps


def default_skill_md(name: str, interface_key: str, caps: list[str]) -> str:
    caps_lines = "\n".join(f"- {c}" for c in caps) or "- context.read"
    return f"""# Purpose
{name}: one bounded cognitive transformation implementing {interface_key}.

# Inputs
- Task Charter
- Input artifact per interface contract
- Evidence Bundle
- Applicable Rules

# Outputs
Return a typed Artifact Patch only.

# Allowed Capabilities
{caps_lines}

# Procedure
1. Read the current artifact.
2. Search the active Knowledge Space for relevant evidence.
3. Produce structured output.
4. Attach evidence references.
5. Return a patch only.

# Quality Criteria
- Every claim is testable or marked as assumption.
- No unsupported provider tool references.
- Evidence is attached where available.
"""


def sr_generator_md() -> str:
    return """# Purpose
Generate system requirements from the current problem understanding artifact.

# Inputs
- Task Charter
- ProblemUnderstandingArtifact@1
- Evidence Bundle
- Applicable Rules

# Outputs
Return SystemRequirementsPatch@1.

# Allowed Capabilities
- context.search
- context.read
- artifact.read
- artifact.patch

# Procedure
1. Read the current artifact.
2. Identify missing technical constraints.
3. Search the active Knowledge Space for relevant evidence.
4. Generate atomic, testable requirements.
5. Attach evidence references.
6. Return a patch only.

# Quality Criteria
- Every requirement is testable.
- No unsupported assumptions.
- Evidence is attached where available.
"""


def _interface_index() -> tuple[set[str], dict[str, list[str]]]:
    return interface_index()


def empty_evidence_test() -> SkillTestCase:
    return SkillTestCase(
        key="empty-evidence",
        name="Empty evidence bundle",
        mode="CONTRACT",
        status="PENDING",
    )


def quality_scaffold_files() -> list[SkillFile]:
    return [
        SkillFile(path="examples/", kind="folder", media_type="inode/directory"),
        SkillFile(
            path="examples/example-output.json",
            media_type="application/json",
            content_text="{}\n",
        ),
    ]


def ensure_quality_scaffold(
    files: list[SkillFile],
    test_cases: list[SkillTestCase],
) -> tuple[list[SkillFile], list[SkillTestCase]]:
    """Ensure examples/ + empty-evidence regression test exist (idempotent)."""
    out_files = list(files)
    out_tests = list(test_cases)
    if not any(f.path.startswith("examples/") for f in out_files):
        out_files.extend(quality_scaffold_files())
    if not any("empty" in t.key.lower() or "empty" in t.name.lower() for t in out_tests):
        out_tests.append(empty_evidence_test())
    return out_files, out_tests


def _pg_session():
    from src.platform.db.session import session_scope

    return session_scope()


def _repo(session):
    from src.platform.skills.repository import SkillsRepository

    return SkillsRepository(session)


_SEEDING = False
_PG_SEED_CHECKED = False


def reset_skills_seed_cache() -> None:
    global _PG_SEED_CHECKED
    _PG_SEED_CHECKED = False


def ensure_skills_seeded() -> None:
    global _SEEDING, _PG_SEED_CHECKED
    if skills_use_postgres():
        from src.platform.db.schema import ensure_schema

        ensure_schema()
        if _PG_SEED_CHECKED:
            return
        if _SEEDING:
            return
        _SEEDING = True
        try:
            records, versions = _build_seed()
            with _pg_session() as session:
                seeded = _repo(session).seed_if_empty(records, versions)
                if seeded:
                    logger.info("Skills subsystem seeded into PostgreSQL")
            _PG_SEED_CHECKED = True
        finally:
            _SEEDING = False
        return

    marker = _path(".seeded_skills_v1")
    if marker.exists() and _path("skill_records.json").exists() and _path("skill_versions.json").exists():
        return
    if _SEEDING:
        return
    _SEEDING = True
    try:
        _seed_skills_unlocked()
    finally:
        _SEEDING = False


def build_seed_catalog() -> tuple[list[SkillRecord], list[SkillVersion]]:
    _, caps_map = interface_index()
    records: list[SkillRecord] = []
    versions: list[SkillVersion] = []

    seeds = [
        {
            "key": "team-system-requirements",
            "name": "System Requirements Generator",
            "description": "Generates structured, evidence-backed system requirements from a normalized problem artifact.",
            "skill_type": "TEAM",
            "owner": "Payments Analysis",
            "interface": "analysis.system_requirements.generate@1",
            "input": "ProblemUnderstandingArtifact@1",
            "output": "SystemRequirementsPatch@1",
            "published": "1.4.0",
            "draft": "1.5.0",
            "runs": 0,
            "success": 0.0,
            "md": sr_generator_md(),
            "bindings": [
                SkillBindingRef(scope="PLAYBOOK_STEP", target="System Requirements / Generate Requirements", priority=500),
                SkillBindingRef(scope="KNOWLEDGE_SPACE", target="Payments", priority=300),
            ],
            "tests": [
                SkillTestCase(key="complete-evidence", name="Generate from complete evidence", mode="SANDBOX", status="PASSED", duration_s=18.2),
                SkillTestCase(key="missing-architecture", name="Missing architecture context", mode="MOCK_CAPABILITIES", status="PASSED", duration_s=7.4),
                SkillTestCase(key="empty-evidence", name="Empty evidence bundle", mode="CONTRACT", status="MISSING"),
            ],
        },
        {
            "key": "business-requirements",
            "name": "Business Requirements",
            "description": (
                "Write product requirements documents (PRDs), feature specifications, "
                "and business requirements from a work item / task context."
            ),
            "skill_type": "CORE",
            "owner": "Product Analysis",
            "interface": "analysis.business_requirements.generate@1",
            "input": "WorkItem@1",
            "output": "ArtifactPatch@1",
            "published": "1.0.0",
            "draft": None,
            "runs": 0,
            "success": 0.0,
            "md": None,
            "bindings": [
                SkillBindingRef(
                    scope="PLAYBOOK_STEP",
                    target="Business Requirements / Generate BRD",
                    priority=500,
                ),
            ],
            "tests": [
                SkillTestCase(key="happy-path", name="Generate BRD from work item", mode="SANDBOX", status="PASSED", duration_s=12.4),
            ],
        },
        {
            "key": "core-problem-understanding",
            "name": "Problem Understanding",
            "description": "Transforms a work item into a scoped problem-understanding artifact.",
            "skill_type": "CORE",
            "owner": "Architecture Enablement",
            "interface": "analysis.problem.understand@1",
            "input": "WorkItem@1",
            "output": "ProblemUnderstandingPatch@1",
            "published": "2.1.0",
            "draft": None,
            "runs": 0,
            "success": 0.0,
            "md": None,
            "bindings": [
                SkillBindingRef(scope="PLAYBOOK_STEP", target="System Requirements / Understand problem", priority=400),
            ],
            "tests": [
                SkillTestCase(key="happy-path", name="Happy path work item", mode="SANDBOX", status="PASSED", duration_s=9.1),
            ],
        },
        {
            "key": "corporate-requirements-quality",
            "name": "Requirements Quality Review",
            "description": "Reviews requirements for ambiguity, testability, consistency and evidence coverage.",
            "skill_type": "CORPORATE",
            "owner": "Compliance",
            "interface": "analysis.requirements.validate@2",
            "input": "RequirementsArtifact@1",
            "output": "QualityReviewPatch@1",
            "published": "1.8.2",
            "draft": None,
            "runs": 0,
            "success": 0.0,
            "md": None,
            "bindings": [],
            "tests": [],
            "extra_files": [
                SkillFile(path="templates/", kind="folder", media_type="inode/directory"),
                SkillFile(
                    path="templates/review-checklist.md",
                    media_type="text/markdown",
                    content_text="# Review checklist\n- Ambiguity\n- Testability\n- Evidence\n",
                ),
            ],
        },
        {
            "key": "team-payments-enricher",
            "name": "Payments Domain Enricher",
            "description": "Adds payments-domain constraints and terminology to analysis artifacts.",
            "skill_type": "TEAM",
            "owner": "Payments Analysis",
            "interface": "analysis.requirements.improve@1",
            "input": "Artifact@1",
            "output": "EnrichmentPatch@1",
            "published": None,
            "draft": "0.7.0",
            "runs": 0,
            "success": 0.0,
            "md": None,
            "bindings": [],
            "tests": [],
        },
        {
            "key": "core-code-review",
            "name": "Code Review",
            "description": "Performs policy-aware review of a repository change and returns structured findings.",
            "skill_type": "CORE",
            "owner": "Platform Engineering",
            "interface": "development.code.review@1",
            "input": "ChangeSet@1",
            "output": "CodeReviewFindings@1",
            "published": "3.0.1",
            "draft": None,
            "runs": 0,
            "success": 0.0,
            "md": None,
            "bindings": [],
            "tests": [],
        },
        {
            "key": "imported-legacy-requirements",
            "name": "Legacy Skill Import",
            "description": "Imported legacy requirement generation prompt pending migration to typed contracts.",
            "skill_type": "IMPORTED",
            "owner": "Migration",
            "interface": "analysis.business_requirements.generate@1",
            "input": "WorkItem@1",
            "output": "ArtifactPatch@1",
            "published": "1.0.0",
            "draft": None,
            "deprecated": True,
            "runs": 0,
            "success": 0.0,
            "md": None,
            "bindings": [],
            "tests": [],
        },
    ]

    for seed in seeds:
        skill_id = seed_id("skill", seed["key"])
        caps = caps_map.get(seed["interface"], ["context.read"])
        md = seed["md"] or default_skill_md(seed["name"], seed["interface"], caps)
        manifest = {
            "apiVersion": "platform.skills/v1",
            "kind": "Skill",
            "metadata": {"key": seed["key"]},
            "spec": {
                "version": seed["published"] or seed["draft"] or "0.1.0",
                "implements": [seed["interface"]],
                "inputContract": seed["input"],
                "outputContract": seed["output"],
                "allowedCapabilities": list(caps),
            },
        }
        try:
            import yaml

            manifest_text = yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False)
        except Exception:
            import json as _json

            manifest_text = _json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
        files = [
            SkillFile(path="SKILL.md", media_type="text/markdown", content_text=md),
            SkillFile(path="manifest.yaml", media_type="text/yaml", content_text=manifest_text),
            SkillFile(path="schemas/", kind="folder", media_type="inode/directory"),
            SkillFile(path="schemas/input.schema.json", media_type="application/json", content_text="{}"),
            SkillFile(path="schemas/output.schema.json", media_type="application/json", content_text="{}"),
            SkillFile(path="tests/", kind="folder", media_type="inode/directory"),
            SkillFile(path="tests/cases.yaml", media_type="text/yaml", content_text=""),
        ]
        for extra in seed.get("extra_files") or []:
            files.append(extra)
        tests = list(seed["tests"] or [])
        files, tests = ensure_quality_scaffold(files, tests)

        rec = SkillRecord(
            id=skill_id,
            key=seed["key"],
            name=seed["name"],
            description=seed["description"],
            skill_type=seed["skill_type"],
            status="deprecated" if seed.get("deprecated") else ("draft" if not seed["published"] else "active"),
            owner_team=seed["owner"],
            runs_30d=seed["runs"],
            success_rate=seed["success"],
            bindings=seed["bindings"],
        )

        if seed["published"]:
            pub_manifest = dict(manifest)
            pub_manifest["spec"] = dict(manifest["spec"])
            pub_manifest["spec"]["version"] = seed["published"]
            pub = SkillVersion(
                id=seed_id("skv", f"{seed['key']}-{seed['published']}"),
                skill_id=skill_id,
                semantic_version=seed["published"],
                status="DEPRECATED" if seed.get("deprecated") else "PUBLISHED",
                skill_markdown=md,
                manifest=pub_manifest,
                package_checksum=checksum(md, pub_manifest, files),
                interface_key=seed["interface"],
                input_contract_key=seed["input"],
                output_contract_key=seed["output"],
                allowed_capabilities=list(caps),
                files=files,
                test_cases=tests,
                published_at=datetime.utcnow(),
            )
            report = validate_version(pub, known_interfaces={seed["interface"]}, interface_capabilities={seed["interface"]: caps})
            pub.validation_report = report
            pub.validation_status = "valid" if report["valid"] else "invalid"
            if report.get("warnings") and report["valid"]:
                pub.validation_status = "warning"
            versions.append(pub)
            if pub.status == "PUBLISHED":
                rec.current_published_version_id = pub.id

        if seed["draft"]:
            draft_md = md
            draft_manifest = dict(manifest)
            draft_manifest["spec"] = dict(manifest["spec"])
            draft_manifest["spec"]["version"] = seed["draft"]
            draft_files = [f.model_copy(deep=True) for f in files]
            draft = SkillVersion(
                id=seed_id("skv", f"{seed['key']}-{seed['draft']}"),
                skill_id=skill_id,
                semantic_version=seed["draft"],
                status="DRAFT",
                skill_markdown=draft_md,
                manifest=draft_manifest,
                package_checksum=checksum(draft_md, draft_manifest, draft_files),
                interface_key=seed["interface"],
                input_contract_key=seed["input"],
                output_contract_key=seed["output"],
                allowed_capabilities=list(caps),
                files=draft_files,
                test_cases=[t.model_copy(deep=True) for t in tests],
            )
            report = validate_version(draft, known_interfaces={seed["interface"]}, interface_capabilities={seed["interface"]: caps})
            draft.validation_report = report
            draft.validation_status = "warning" if report.get("warnings") else ("valid" if report["valid"] else "invalid")
            versions.append(draft)
            rec.current_draft_version_id = draft.id

        records.append(rec)

    return records, versions


