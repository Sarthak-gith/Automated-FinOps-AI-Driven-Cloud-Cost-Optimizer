"""Provider adapter that delegates to deterministic local synthetic telemetry."""

from datetime import datetime

from sqlalchemy.orm import Session

from app.providers.base import TelemetryProvider
from app.simulation.simulator import generate_latest_metrics, seed_demo_data


class SimulatorProvider:
    name = "simulated"

    def seed(self, session: Session, resource_count: int = 20,
             history_days: int = 30) -> dict[str, int]:
        return seed_demo_data(session, resource_count, history_days)

    def collect_latest(self, session: Session, now: datetime | None = None) -> int:
        return generate_latest_metrics(session, now)
