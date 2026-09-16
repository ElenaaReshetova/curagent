"""Artifact contract registry and compatibility helpers."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from src.platform.contracts.models import ArtifactContract
from src.platform.contracts.seed import (
    INTERFACE_CONTRACTS,
    build_artifact_contracts,
    default_interface_contracts,
)


def parse_contract_key(key: str) -> tuple[str, int]:
    if "@" not in key:
        raise ValueError(f"Invalid contract key: {key}")
    name, raw_ver = key.rsplit("@", 1)
    return name, int(raw_ver)


def patch_to_artifact(name: str) -> str | None:
    if name.endswith("Patch"):
        return f"{name[:-5]}Artifact"
    return None


@lru_cache(maxsize=1)
def _contract_map() -> dict[str, ArtifactContract]:
    try:
        from src.platform.store import list_artifact_contracts

        items = list_artifact_contracts()
    except Exception:
        items = build_artifact_contracts()
    if not items:
        items = build_artifact_contracts()
    return {item.key: item for item in items}


def list_contracts() -> list[ArtifactContract]:
    return sorted(_contract_map().values(), key=lambda c: c.key)


def get_contract(key: str) -> ArtifactContract | None:
    return _contract_map().get(key)


def known_contract_keys() -> set[str]:
    return set(_contract_map())


def interface_contracts(interface_key: str) -> tuple[str, str]:
    return default_interface_contracts(interface_key)


def interface_contract_index() -> dict[str, tuple[str, str]]:
    index = {key: value for key, value in INTERFACE_CONTRACTS.items()}
    try:
        from src.platform.store import list_skill_interfaces

        for iface in list_skill_interfaces():
            if iface.input_contract_key and iface.output_contract_key:
                index[iface.key] = (iface.input_contract_key, iface.output_contract_key)
    except Exception:
        pass
    return index


def contracts_compatible(output_key: str, input_key: str) -> bool:
    if not output_key or not input_key:
        return False
    if output_key == input_key:
        return True
    try:
        out_name, out_ver = parse_contract_key(output_key)
        in_name, in_ver = parse_contract_key(input_key)
    except ValueError:
        return False
    if out_ver != in_ver and not (out_name.endswith("Artifact") and in_name.endswith("Artifact")):
        # Allow v1 artifact to feed v2 when names match family (SystemRequirements v1 -> v2).
        if not (out_name == in_name and out_ver < in_ver):
            pass
    if patch_to_artifact(out_name) == in_name:
        return True
    out_contract = get_contract(output_key)
    if out_contract and input_key in out_contract.satisfies:
        return True
    in_contract = get_contract(input_key)
    if in_contract and output_key in in_contract.accepts:
        return True
    # Generic artifact accepts typed patches/artifacts of same major family.
    if input_key == "Artifact@1" and output_key.endswith("@1"):
        return True
    return False


def validate_contract_references(
    input_key: str,
    output_key: str,
    *,
    interface_key: str | None = None,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    known = known_contract_keys()

    if not input_key:
        errors.append({"code": "MISSING_INPUT_CONTRACT", "message": "Input contract is required"})
    elif input_key not in known:
        errors.append({
            "code": "UNKNOWN_INPUT_CONTRACT",
            "message": f"Input contract '{input_key}' is not registered",
        })

    if not output_key:
        errors.append({"code": "MISSING_OUTPUT_CONTRACT", "message": "Output contract is required"})
    elif output_key not in known:
        errors.append({
            "code": "UNKNOWN_OUTPUT_CONTRACT",
            "message": f"Output contract '{output_key}' is not registered",
        })

    if interface_key:
        expected_in, expected_out = interface_contracts(interface_key)
        if input_key and input_key != expected_in:
            warnings.append({
                "code": "INPUT_CONTRACT_INTERFACE_MISMATCH",
                "message": (
                    f"Input contract '{input_key}' differs from interface "
                    f"default '{expected_in}'"
                ),
            })
        if output_key and output_key != expected_out:
            warnings.append({
                "code": "OUTPUT_CONTRACT_INTERFACE_MISMATCH",
                "message": (
                    f"Output contract '{output_key}' differs from interface "
                    f"default '{expected_out}'"
                ),
            })

    return errors, warnings


def validate_payload(contract_key: str, payload: Any) -> list[str]:
    contract = get_contract(contract_key)
    if not contract:
        return [f"Unknown contract: {contract_key}"]
    schema = contract.json_schema or {}
    errors: list[str] = []
    expected_type = schema.get("type")
    if expected_type == "object":
        if not isinstance(payload, dict):
            return [f"{contract_key}: expected object, got {type(payload).__name__}"]
        for field in schema.get("required", []):
            if field not in payload:
                errors.append(f"{contract_key}: missing required field '{field}'")
        declared = payload.get("type")
        if declared and declared != contract.key.rsplit("@", 1)[0]:
            errors.append(
                f"{contract_key}: payload.type '{declared}' does not match contract"
            )
    return errors
