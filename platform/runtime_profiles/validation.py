"""Runtime Profile validation (structural MVP)."""

from __future__ import annotations

from typing import Any

from src.platform.runtime_profiles.models import RuntimeProfileVersion

PROHIBITED_INLINE = ("api_key", "password", "secret=", "sk-", "Bearer ")


def validate_version(version: RuntimeProfileVersion) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    if not version.model:
        errors.append({"code": "MODEL_REQUIRED", "message": "Model is required"})
    if not version.provider:
        errors.append({"code": "PROVIDER_REQUIRED", "message": "Provider is required"})

    if version.profile_type == "PRODUCTION" and version.sandbox in ("NONE", "PROCESS"):
        errors.append({
            "code": "PRODUCTION_SANDBOX",
            "message": "Production profiles require CONTAINER or stronger sandbox",
        })

    if version.provider in ("QWEN_CODE_CLI", "OPENAI_API") and not version.secret_ref:
        warnings.append({
            "code": "SECRET_REF_MISSING",
            "message": "Secret reference recommended for cloud providers",
        })

    if version.secret_ref and any(tok in version.secret_ref.lower() for tok in ("password", "apikey=")):
        errors.append({"code": "INLINE_SECRET", "message": "Inline secrets are not allowed"})

    raw = f"{version.secret_ref} {version.model} {version.provider}".lower()
    for token in PROHIBITED_INLINE:
        if token in raw and not version.secret_ref.startswith(("vault://", "secret://")):
            errors.append({"code": "INLINE_CREDENTIAL", "message": f"Possible inline credential: {token}"})

    if version.profile_type == "RESTRICTED" and version.network_policy != "ALLOW_CAPABILITY_GATEWAY_ONLY":
        warnings.append({
            "code": "RESTRICTED_NETWORK",
            "message": "Restricted profiles should use capability gateway only",
        })

    valid = len(errors) == 0
    return {
        "valid": valid,
        "status": "valid" if valid and not warnings else ("warning" if valid else "invalid"),
        "errors": errors,
        "warnings": warnings,
    }
