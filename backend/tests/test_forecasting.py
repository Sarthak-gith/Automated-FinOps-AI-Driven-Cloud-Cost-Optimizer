from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.database import Base, make_engine
from app.db.models import Forecast
from app.forecasting.service import generate_forecast
from app.simulation.simulator import seed_demo_data


def test_forecast_persists_points_and_reuses_recent_cache():
    engine = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    now = datetime(2026, 1, 31, 12, tzinfo=timezone.utc)
    with Session(engine) as session:
        seed_demo_data(session, resource_count=1, history_days=7, now=now)
        first = generate_forecast(session, "sim-general-001", horizon_hours=24, force=True, now=now)
        assert first.status == "available"
        assert first.model in {"Prophet", "ARIMA fallback"}
        assert len(first.points) == 24
        assert all(0 <= point["lower_bound"] <= point["predicted"] <= point["upper_bound"] <= 100
                   for point in first.points)
        assert session.scalar(select(func.count()).select_from(Forecast)) == 24
        cached = generate_forecast(session, "sim-general-001", horizon_hours=24, now=now)
        assert cached.generated_at == first.generated_at
        assert cached.model == first.model


def test_forecast_reports_insufficient_history():
    engine = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_demo_data(session, resource_count=1, history_days=1,
                       now=datetime(2026, 1, 31, 12, tzinfo=timezone.utc))
        result = generate_forecast(session, "sim-general-001", horizon_hours=24, force=True)
        assert result.status == "insufficient_data"
        assert result.points == []
