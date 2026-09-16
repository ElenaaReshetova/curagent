"""Load contextual help concepts from YAML registry."""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from src.platform.help.models import HelpCatalogResponse, HelpConcept, HelpExample

logger = logging.getLogger(__name__)

DEFAULT_LOCALE = "ru-RU"
FALLBACK_LOCALE = "en-US"


def help_dir() -> Path:
    env = os.environ.get("PLATFORM_HELP_DIR")
    if env:
        return Path(env).expanduser().resolve()
    return Path(__file__).resolve().parents[3] / "config" / "help"


def _parse_concept(raw: dict[str, Any], locale: str, *, missing: bool = False) -> HelpConcept:
    example = raw.get("example")
    if isinstance(example, dict):
        example = HelpExample.model_validate(example)
    elif example is None:
        example = None
    else:
        example = HelpExample(title="Example", value=example)
    data = {**raw, "example": example}
    concept = HelpConcept.model_validate(data)
    concept.locale = locale
    concept.missing_translation = missing
    return concept


def _load_locale_file(locale: str) -> dict[str, HelpConcept]:
    root = help_dir() / locale
    concepts: dict[str, HelpConcept] = {}
    if not root.is_dir():
        return concepts
    for path in sorted(root.glob("*.yaml")) + sorted(root.glob("*.yml")):
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception as e:
            logger.warning("Failed to read help file %s: %s", path, e)
            continue
        items = payload.get("concepts") if isinstance(payload, dict) else None
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict) or not item.get("conceptKey"):
                continue
            concept = _parse_concept(item, locale)
            concepts[concept.concept_key] = concept
    return concepts


@lru_cache(maxsize=8)
def load_catalog(locale: str = DEFAULT_LOCALE) -> dict[str, HelpConcept]:
    primary = _load_locale_file(locale)
    if locale == FALLBACK_LOCALE:
        return primary
    fallback = _load_locale_file(FALLBACK_LOCALE)
    merged = dict(fallback)
    for key, concept in fallback.items():
        if key not in primary:
            # Mark fallback entries when requesting non-fallback locale
            merged[key] = concept.model_copy(update={"missing_translation": True, "locale": locale})
    merged.update(primary)
    return merged


def clear_help_cache() -> None:
    load_catalog.cache_clear()


def list_concepts(locale: str = DEFAULT_LOCALE, prefix: str = "") -> HelpCatalogResponse:
    catalog = load_catalog(locale)
    concepts = list(catalog.values())
    if prefix:
        concepts = [c for c in concepts if c.concept_key.startswith(prefix)]
    concepts.sort(key=lambda c: c.concept_key)
    missing = [c.concept_key for c in concepts if c.missing_translation]
    return HelpCatalogResponse(
        locale=locale,
        fallback_locale=FALLBACK_LOCALE,
        concepts=concepts,
        missing_keys=missing,
    )


def get_concept(concept_key: str, locale: str = DEFAULT_LOCALE) -> HelpConcept | None:
    return load_catalog(locale).get(concept_key)
