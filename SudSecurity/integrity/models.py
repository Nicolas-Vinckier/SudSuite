"""Modèles publics de Sud Integrity."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class IntegrityIssue:
    path: str
    kind: str
    detail: str


@dataclass
class IntegrityReport:
    checked_files: int = 0
    unchanged_files: int = 0
    issues: list[IntegrityIssue] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not self.issues

    def by_kind(self, kind: str) -> list[IntegrityIssue]:
        return [issue for issue in self.issues if issue.kind == kind]
