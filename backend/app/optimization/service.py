"""Transparent, deterministic optimization rules over recent metric history."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Recommendation, Resource, ResourceMetric

HOURS_PER_MONTH = 730
IDLE_AVG_CPU = 8.0
IDLE_MAX_CPU = 15.0
RIGHTSIZE_AVG_CPU = 30.0
RIGHTSIZE_P95_CPU = 55.0


def _recommendation(resource: Resource, kind: str, rationale: str, savings_cents: int,
                    risk: str, now: datetime) -> Recommendation:
    return Recommendation(
        id=f"rec-{resource.id}-{kind}", resource_id=resource.id, kind=kind,
        status="pending", rationale=rationale,
        estimated_monthly_savings_cents=max(0, savings_cents), risk_level=risk,
        created_at=now,
    )


def analyze_resource(session: Session, resource: Resource, since: datetime,
                     now: datetime) -> list[Recommendation]:
    if resource.status != "running" or resource.category in {"storage", "network"}:
        return []
    values = session.execute(select(ResourceMetric.cpu_percent).where(
        ResourceMetric.resource_id == resource.id,
        ResourceMetric.observed_at >= since,
        ResourceMetric.observed_at <= now,
    ).order_by(ResourceMetric.observed_at)).scalars().all()
    if len(values) < 24 * 3:
        return []
    average = sum(values) / len(values)
    ordered = sorted(values)
    p95 = ordered[min(len(ordered) - 1, int((len(ordered) - 1) * 0.95))]
    highest = max(values)
    existing = {row.kind: row for row in session.scalars(select(Recommendation).where(
        Recommendation.resource_id == resource.id,
        Recommendation.status.in_(["pending", "approved", "rejected", "executed"]),
    )).all()}
    candidates = []
    prod = str(resource.labels.get("environment", "")).lower() == "prod"
    is_idle = average < IDLE_AVG_CPU and highest < IDLE_MAX_CPU
    if is_idle and "idle-stop" not in existing:
        percent = 0.65 if prod else 0.80
        savings = int(resource.hourly_cost_cents * HOURS_PER_MONTH * percent)
        candidates.append(_recommendation(
            resource, "idle-stop",
            f"Over {len(values)} recent hourly observations, mean CPU was {average:.1f}% "
            f"and maximum CPU was {highest:.1f}%. A simulated stop may save about {percent:.0%} "
            "of the resource's monthly run cost; this estimate excludes restart and dependency costs.",
            savings, "high" if prod else "medium", now))
    elif not is_idle and average < RIGHTSIZE_AVG_CPU and p95 < RIGHTSIZE_P95_CPU and "right-size" not in existing:
        percent = 0.25
        savings = int(resource.hourly_cost_cents * HOURS_PER_MONTH * percent)
        candidates.append(_recommendation(
            resource, "right-size",
            f"Over {len(values)} recent hourly observations, mean CPU was {average:.1f}% "
            f"and 95th-percentile CPU was {p95:.1f}%. A simulated one-size reduction is "
            "estimated at 25% lower compute cost; capacity and performance should be reviewed.",
            savings, "high" if prod else "low", now))
    return candidates


def generate_recommendations(session: Session, lookback_days: int = 7,
                             now: datetime | None = None) -> list[Recommendation]:
    if not 1 <= lookback_days <= 30:
        raise ValueError("lookback_days must be between 1 and 30")
    now = now or datetime.now(timezone.utc)
    since = now - timedelta(days=lookback_days)
    resources = session.scalars(select(Resource).order_by(Resource.id)).all()
    results = []
    for resource in resources:
        rows = analyze_resource(session, resource, since, now)
        session.add_all(rows)
        results.extend(rows)
    session.commit()
    return results


def list_recommendations(session: Session, status: str | None = None):
    query = select(Recommendation).order_by(Recommendation.created_at.desc())
    if status:
        query = query.where(Recommendation.status == status)
    return session.scalars(query).all()
