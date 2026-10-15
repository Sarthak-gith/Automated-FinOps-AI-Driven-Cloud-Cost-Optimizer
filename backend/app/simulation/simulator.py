"""Repeatable local resource and metric generation; never calls cloud APIs."""

from datetime import datetime, timedelta, timezone
import math
import random

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Resource, ResourceMetric

SEED = 20250308
REGIONS = ("us-east-sim-1", "eu-west-sim-1", "ap-south-sim-1")
PROFILES = (
    ("general", "sim.vm.general", "small", 9, "stable"),
    ("compute", "sim.vm.compute", "medium", 22, "growing"),
    ("memory", "sim.vm.memory", "large", 31, "spiky"),
    ("storage", "sim.volume.ssd", "500gb", 4, "storage"),
    ("network", "sim.workload.network", "medium", 18, "daily"),
)


def _bounded(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 2)


def _profile_values(profile: str, day: int, hour: int, rng: random.Random):
    daily = math.sin((hour - 7) * math.tau / 24)
    weekly = math.sin(day * math.tau / 7)
    noise = rng.gauss(0, 3.0)
    if profile == "idle":
        cpu = 2 + abs(noise) * 0.35
    elif profile == "growing":
        cpu = 24 + day * 0.48 + daily * 9 + noise
    elif profile == "spiky":
        cpu = 32 + daily * 8 + noise + (rng.uniform(25, 48) if rng.random() < 0.035 else 0)
    elif profile == "stable":
        cpu = 36 + weekly * 3 + daily * 5 + noise
    elif profile == "storage":
        cpu = 0.5 + abs(noise) * 0.2
    else:
        cpu = 28 + daily * 16 + weekly * 4 + noise
    memory = 22 + cpu * 0.58 + rng.gauss(0, 4)
    storage = 25 + day * 0.18 + rng.gauss(0, 1.4)
    network = max(0.05, (cpu / 100) * rng.uniform(2, 24) + abs(daily) * 2)
    if profile == "storage":
        storage = 46 + day * 0.28 + rng.gauss(0, 1.2)
    return _bounded(cpu), _bounded(memory), _bounded(storage), round(network, 3)


def _resource_specs(count: int):
    profiles = ["idle", "stable", "growing", "spiky", "daily"]
    for i in range(count):
        category, instance_type, size, cents, _base = PROFILES[i % len(PROFILES)]
        profile = profiles[(i // len(PROFILES)) % len(profiles)]
        if category == "storage":
            profile = "storage"
        yield i, category, instance_type, size, cents, profile


def seed_demo_data(session: Session, resource_count: int = 20, history_days: int = 30,
                   now: datetime | None = None) -> dict[str, int]:
    """Insert deterministic resources/history once; subsequent calls are no-ops."""
    if resource_count < 1 or resource_count > 30:
        raise ValueError("resource_count must be between 1 and 30")
    if history_days < 1 or history_days > 90:
        raise ValueError("history_days must be between 1 and 90")
    if session.scalar(select(Resource.id).limit(1)) is not None:
        return {"resources": 0, "metrics": 0, "already_seeded": 1}

    now = now or datetime.now(timezone.utc)
    now = now.replace(minute=0, second=0, microsecond=0)
    resources, metrics = [], []
    hours = history_days * 24
    for i, category, instance_type, size, cents, profile in _resource_specs(resource_count):
        rid = f"sim-{category}-{i + 1:03d}"
        resources.append(Resource(
            id=rid, name=f"sim-{category}-{i + 1:02d}", provider="simulated",
            region=REGIONS[i % len(REGIONS)], category=category, instance_type=instance_type,
            size=size, status="running", hourly_cost_cents=cents,
            created_at=now - timedelta(days=history_days + 5 + i),
            labels={"environment": "demo", "team": ("platform", "analytics", "product")[i % 3],
                    "simulated": "true", "profile": profile},
        ))
        rng = random.Random(SEED + i)
        for step in range(hours):
            observed = now - timedelta(hours=hours - step)
            values = _profile_values(profile, step // 24, observed.hour, rng)
            metrics.append(ResourceMetric(resource_id=rid, observed_at=observed,
                                          cpu_percent=values[0], memory_percent=values[1],
                                          storage_percent=values[2], network_mbps=values[3]))
    session.add_all(resources)
    session.add_all(metrics)
    session.commit()
    return {"resources": len(resources), "metrics": len(metrics), "already_seeded": 0}


def generate_latest_metrics(session: Session, now: datetime | None = None) -> int:
    """Append a current hourly sample for all resources without altering history."""
    now = (now or datetime.now(timezone.utc)).replace(minute=0, second=0, microsecond=0)
    inserted = 0
    resources = session.scalars(select(Resource).order_by(Resource.id)).all()
    for resource in resources:
        exists = session.scalar(select(ResourceMetric.id).where(
            ResourceMetric.resource_id == resource.id,
            ResourceMetric.observed_at == now,
        ))
        if exists is not None:
            continue
        profile = resource.labels.get("profile", "stable")
        day = max(0, (now.date() - resource.created_at.date()).days - 5)
        rng = random.Random(f"{SEED}:{resource.id}:{now.isoformat()}")
        cpu, memory, storage, network = _profile_values(profile, day, now.hour, rng)
        session.add(ResourceMetric(resource_id=resource.id, observed_at=now, cpu_percent=cpu,
                                   memory_percent=memory, storage_percent=storage,
                                   network_mbps=network))
        inserted += 1
    session.commit()
    return inserted
