from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.database import Base, make_engine
from app.db.models import Resource, ResourceMetric
from app.simulation.simulator import generate_latest_metrics, seed_demo_data


def test_seed_is_deterministic_idempotent_and_latest_appends():
    engine = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    now = datetime(2026, 1, 31, 12, tzinfo=timezone.utc)
    with Session(engine) as session:
        result = seed_demo_data(session, resource_count=10, history_days=30, now=now)
        assert result == {"resources": 10, "metrics": 7200, "already_seeded": 0}
        assert seed_demo_data(session, resource_count=10, history_days=30, now=now)["already_seeded"] == 1
        assert session.scalar(select(func.count()).select_from(Resource)) == 10
        assert session.scalar(select(func.count()).select_from(ResourceMetric)) == 7200
        previous = session.scalar(select(func.count()).select_from(ResourceMetric))
        assert generate_latest_metrics(session, now=now + __import__("datetime").timedelta(hours=1)) == 10
        assert session.scalar(select(func.count()).select_from(ResourceMetric)) == previous + 10
        assert generate_latest_metrics(session, now=now + __import__("datetime").timedelta(hours=1)) == 0
        assert session.scalar(select(Resource.provider).limit(1)) == "simulated"


def test_seed_limits_are_validated():
    engine = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        try:
            seed_demo_data(session, resource_count=31)
        except ValueError as error:
            assert "resource_count" in str(error)
        else:
            raise AssertionError("expected configuration validation")
