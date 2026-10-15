"""Persisted CPU forecasting with Prophet and an explicit ARIMA fallback."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Forecast, Resource, ResourceMetric

MIN_HISTORY_POINTS = 48
CACHE_TTL = timedelta(hours=6)


@dataclass
class ForecastResult:
    resource_id: str
    status: str
    model: str | None
    generated_at: datetime | None
    points: list[dict]
    mae: float | None = None
    rmse: float | None = None
    message: str | None = None


def _history(session: Session, resource_id: str) -> pd.DataFrame:
    observations = session.scalars(select(ResourceMetric).where(
        ResourceMetric.resource_id == resource_id
    ).order_by(ResourceMetric.observed_at)).all()
    frame = pd.DataFrame([{"ds": row.observed_at, "y": row.cpu_percent} for row in observations])
    if frame.empty:
        return frame
    frame["ds"] = pd.to_datetime(frame["ds"], utc=True).dt.tz_localize(None)
    frame = frame.dropna().groupby("ds", as_index=False)["y"].mean().sort_values("ds")
    frame["y"] = pd.to_numeric(frame["y"], errors="coerce")
    return frame.dropna(subset=["y"])


def _forecast_prophet(history: pd.DataFrame, horizon_hours: int):
    from prophet import Prophet

    model = Prophet(daily_seasonality=True, weekly_seasonality=True,
                    yearly_seasonality=False, interval_width=0.9)
    model.fit(history)
    future = model.make_future_dataframe(periods=horizon_hours, freq="h", include_history=False)
    predicted = model.predict(future)[["ds", "yhat", "yhat_lower", "yhat_upper"]]
    return model, predicted


def _forecast_arima(history: pd.DataFrame, horizon_hours: int):
    from statsmodels.tsa.arima.model import ARIMA

    series = history.set_index("ds")["y"].asfreq("h").interpolate(limit_direction="both")
    fitted = ARIMA(series, order=(2, 1, 2)).fit()
    forecast = fitted.get_forecast(steps=horizon_hours)
    bounds = forecast.conf_int(alpha=0.1)
    index = pd.date_range(series.index[-1] + pd.Timedelta(hours=1), periods=horizon_hours, freq="h")
    frame = pd.DataFrame({"ds": index, "yhat": forecast.predicted_mean.to_numpy(),
                          "yhat_lower": bounds.iloc[:, 0].to_numpy(),
                          "yhat_upper": bounds.iloc[:, 1].to_numpy()})
    return fitted, frame


def _fit(history: pd.DataFrame, horizon_hours: int):
    try:
        fitted, prediction = _forecast_prophet(history, horizon_hours)
        return "Prophet", fitted, prediction
    except Exception as prophet_error:
        try:
            fitted, prediction = _forecast_arima(history, horizon_hours)
            return "ARIMA fallback", fitted, prediction
        except Exception as arima_error:
            raise RuntimeError(f"Prophet failed ({prophet_error}); ARIMA fallback failed ({arima_error})") from arima_error


def _evaluate(history: pd.DataFrame) -> tuple[float | None, float | None]:
    if len(history) < MIN_HISTORY_POINTS + 24:
        return None, None
    holdout = min(168, max(24, len(history) // 5))
    train, test = history.iloc[:-holdout].copy(), history.iloc[-holdout:].copy()
    if len(train) < MIN_HISTORY_POINTS:
        return None, None
    try:
        _model_name, _model, prediction = _fit(train, len(test))
        actual = test["y"].to_numpy()
        predicted = prediction["yhat"].to_numpy()[:len(test)]
        return (round(float(mean_absolute_error(actual, predicted)), 3),
                round(float(np.sqrt(mean_squared_error(actual, predicted))), 3))
    except Exception:
        return None, None


def _cached(session: Session, resource_id: str, horizon_hours: int, now: datetime):
    latest = session.scalar(select(Forecast.generated_at).where(
        Forecast.resource_id == resource_id, Forecast.metric == "cpu_percent"
    ).order_by(Forecast.generated_at.desc()).limit(1))
    if latest is None:
        return None
    if latest.tzinfo is None:
        latest = latest.replace(tzinfo=timezone.utc)
    if now - latest > CACHE_TTL:
        return None
    forecasts = session.scalars(select(Forecast).where(
        Forecast.resource_id == resource_id, Forecast.metric == "cpu_percent",
        Forecast.generated_at == latest,
    ).order_by(Forecast.target_at).limit(horizon_hours)).all()
    if not forecasts:
        return None
    return [ForecastResult(resource_id, "available", forecasts[0].model_name, latest,
                           [{"timestamp": x.target_at, "predicted": x.predicted,
                             "lower_bound": x.lower_bound, "upper_bound": x.upper_bound}
                            for x in forecasts])]


def generate_forecast(session: Session, resource_id: str, horizon_hours: int = 168,
                      force: bool = False, now: datetime | None = None) -> ForecastResult:
    if not 1 <= horizon_hours <= 168:
        raise ValueError("horizon_hours must be between 1 and 168")
    now = now or datetime.now(timezone.utc)
    resource = session.get(Resource, resource_id)
    if resource is None:
        raise ValueError("resource not found")
    if not force:
        cached = _cached(session, resource_id, horizon_hours, now)
        if cached:
            return cached[0]
    history = _history(session, resource_id)
    if len(history) < MIN_HISTORY_POINTS:
        return ForecastResult(resource_id, "insufficient_data", None, None, [],
                              message=f"At least {MIN_HISTORY_POINTS} valid hourly observations are required.")
    try:
        model_name, _model, prediction = _fit(history, horizon_hours)
        generated_at = now
        mae, rmse = _evaluate(history)
        points = []
        for row in prediction.itertuples(index=False):
            lower = max(0.0, min(100.0, float(row.yhat_lower)))
            upper = max(lower, min(100.0, float(row.yhat_upper)))
            predicted = max(lower, min(upper, float(row.yhat)))
            target_at = pd.Timestamp(row.ds).to_pydatetime().replace(tzinfo=timezone.utc)
            point = {"timestamp": target_at, "predicted": round(predicted, 3),
                     "lower_bound": round(lower, 3), "upper_bound": round(upper, 3)}
            points.append(point)
            session.add(Forecast(resource_id=resource_id, metric="cpu_percent", generated_at=generated_at,
                                 target_at=target_at, predicted=point["predicted"],
                                 lower_bound=point["lower_bound"], upper_bound=point["upper_bound"],
                                 model_name=model_name, status="available"))
        session.commit()
        return ForecastResult(resource_id, "available", model_name, generated_at, points, mae, rmse)
    except Exception as exc:
        session.rollback()
        return ForecastResult(resource_id, "failed", None, None, [],
                              message=f"Forecast failed: {type(exc).__name__}: {exc}")


def latest_forecasts(session: Session, resource_id: str | None = None) -> list[dict]:
    query = select(Forecast).where(Forecast.metric == "cpu_percent")
    if resource_id:
        query = query.where(Forecast.resource_id == resource_id)
    rows = session.scalars(query.order_by(Forecast.generated_at.desc(), Forecast.target_at)).all()
    latest: dict[str, datetime] = {}
    for row in rows:
        latest.setdefault(row.resource_id, row.generated_at)
    return [{"resource_id": row.resource_id, "metric": row.metric,
             "generated_at": row.generated_at, "timestamp": row.target_at,
             "predicted": row.predicted, "lower_bound": row.lower_bound,
             "upper_bound": row.upper_bound, "model": row.model_name,
             "status": row.status, "simulated": True}
            for row in rows if row.generated_at == latest.get(row.resource_id)]
