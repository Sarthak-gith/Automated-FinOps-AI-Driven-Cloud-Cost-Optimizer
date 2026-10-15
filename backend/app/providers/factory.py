"""Select the local provider. Live cloud providers are intentionally unavailable."""

import os

from app.providers.base import TelemetryProvider
from app.providers.simulator import SimulatorProvider


def get_provider() -> TelemetryProvider:
    selected = os.getenv("CLOUD_PROVIDER", "simulated").strip().lower()
    if selected != "simulated":
        raise ValueError("Only CLOUD_PROVIDER=simulated is implemented; no cloud APIs are called")
    return SimulatorProvider()
