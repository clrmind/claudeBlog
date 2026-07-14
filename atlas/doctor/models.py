from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class CheckStatus(IntEnum):
    OK = 0
    WARNING = 1
    ERROR = 2


@dataclass(frozen=True)
class CheckResult:
    name: str
    category: str
    status: CheckStatus
    message: str
    detail: str = ""
