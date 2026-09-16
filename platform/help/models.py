"""Help content registry models."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


AudienceLevel = Literal["BASIC", "ADVANCED", "EXPERT"]


class HelpExample(BaseModel):
    title: str = ""
    value: Any = None


class HelpConcept(BaseModel):
    concept_key: str = Field(alias="conceptKey")
    title: str
    short_description: str = Field(default="", alias="shortDescription")
    full_description: str = Field(default="", alias="fullDescription")
    example: Optional[HelpExample] = None
    recommended_value: str = Field(default="", alias="recommendedValue")
    consequences: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    related_concepts: list[str] = Field(default_factory=list, alias="relatedConcepts")
    documentation_path: str = Field(default="", alias="documentationPath")
    audience_level: AudienceLevel = Field(default="BASIC", alias="audienceLevel")
    locale: str = "ru-RU"
    missing_translation: bool = False

    model_config = {"populate_by_name": True}


class HelpCatalogResponse(BaseModel):
    locale: str
    fallback_locale: str
    concepts: list[HelpConcept]
    missing_keys: list[str] = Field(default_factory=list)
