"""Product errors for the scenario control plane."""

from __future__ import annotations

from typing import Any


class ScenarioError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        http_status: int = 400,
        issues: list[Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.issues = issues or []

    def as_body(self) -> dict[str, Any]:
        return {"error": {"code": self.code, "message": self.message, "issues": self.issues}}
