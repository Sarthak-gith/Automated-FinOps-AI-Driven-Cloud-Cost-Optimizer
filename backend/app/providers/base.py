"""Protocol boundary between application services and telemetry providers."""

from datetime import datetime
from typing import Protocol

from sqlalchemy.orm import Session


class TelemetryProvider(Protocol):
    name: str

    def seed(self, session: Session, resource_count: int = 20,
             history_days: int = 30) -> dict[str, int]: ...

    def collect_latest(self, session: Session, now: datetime | None = None) -> int: ...
