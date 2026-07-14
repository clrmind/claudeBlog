#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class CircuitBreaker:
    failure_threshold: int = 3
    recovery_seconds: int = 900
    failures: int = 0
    opened_at: float | None = None
    state: str = field(default="closed", init=False)

    def allow_request(self) -> bool:
        if self.state == "closed":
            return True

        if self.opened_at is None:
            return False

        if time.time() - self.opened_at >= self.recovery_seconds:
            self.state = "half_open"
            return True

        return False

    def record_success(self) -> None:
        self.failures = 0
        self.opened_at = None
        self.state = "closed"

    def record_failure(self) -> None:
        self.failures += 1

        if self.failures >= self.failure_threshold:
            self.state = "open"
            self.opened_at = time.time()
