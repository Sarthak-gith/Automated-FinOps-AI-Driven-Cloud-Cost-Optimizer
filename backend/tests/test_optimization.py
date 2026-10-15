from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.database import Base, make_engine
from app.db.models import Recommendation, Resource, ResourceMetric
from app.optimization.service import generate_recommendations


def test_idle_resource_recommendation_is_transparent_and_not_duplicated():
    engine = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    now = datetime(2026, 1, 31, 12, tzinfo=timezone.utc)
    with Session(engine) as session:
        resource = Resource(id="sim-general-001", name="demo", provider="simulated",
                            region="us-east-sim-1", category="general",
                            instance_type="sim.vm.general", size="small", status="running",
                            hourly_cost_cents=9, created_at=now - timedelta(days=40),
                            labels={"environment": "demo"})
        session.add(resource)
        for hour in range(168):
            session.add(ResourceMetric(resource_id=resource.id,
                                       observed_at=now - timedelta(hours=167 - hour),
                                       cpu_percent=2.5, memory_percent=15,
                                       storage_percent=35, network_mbps=0.5))
        session.commit()
        recommendations = generate_recommendations(session, now=now)
        assert len(recommendations) == 1
        row = recommendations[0]
        assert row.kind == "idle-stop"
        assert row.estimated_monthly_savings_cents == int(9 * 730 * 0.8)
        assert "168 recent hourly observations" in row.rationale
        assert generate_recommendations(session, now=now) == []
        assert session.scalar(select(func.count()).select_from(Recommendation)) == 1
