from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class VerifyStatus(IntEnum):
    PASS = 0
    FAIL = 1


@dataclass(frozen=True)
class VerifyResult:
    name: str
    status: VerifyStatus
    message: str
    detail: str = ""
