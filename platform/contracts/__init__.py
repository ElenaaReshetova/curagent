"""Artifact contracts — typed skill/graph I/O."""

from src.platform.contracts.models import ArtifactContract
from src.platform.contracts.registry import (
    contracts_compatible,
    get_contract,
    interface_contract_index,
    interface_contracts,
    known_contract_keys,
    list_contracts,
    validate_contract_references,
    validate_payload,
)
from src.platform.contracts.seed import INTERFACE_CONTRACTS, build_artifact_contracts
from src.platform.contracts.validation import validate_graph_contracts

__all__ = [
    "ArtifactContract",
    "INTERFACE_CONTRACTS",
    "build_artifact_contracts",
    "contracts_compatible",
    "get_contract",
    "interface_contract_index",
    "interface_contracts",
    "known_contract_keys",
    "list_contracts",
    "validate_contract_references",
    "validate_graph_contracts",
    "validate_payload",
]
