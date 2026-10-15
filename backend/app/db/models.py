"""Relational schema for simulated resources, decisions, and audit history."""

from datetime import datetime, timezone

from sqlalchemy import (Boolean, CheckConstraint, DateTime, ForeignKey, Index,
                        Integer, JSON, String, Text, UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(24), default="viewer")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    audit_events: Mapped[list["AuditEvent"]] = relationship(back_populates="user")


class Resource(Base):
    __tablename__ = "resources"
    __table_args__ = (CheckConstraint("hourly_cost_cents >= 0"),)
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    provider: Mapped[str] = mapped_column(String(40), default="simulated")
    region: Mapped[str] = mapped_column(String(40))
    category: Mapped[str] = mapped_column(String(32), index=True)
    instance_type: Mapped[str] = mapped_column(String(64))
    size: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(24), default="running", index=True)
    hourly_cost_cents: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    labels: Mapped[dict] = mapped_column(JSON, default=dict)
    metrics: Mapped[list["ResourceMetric"]] = relationship(back_populates="resource", cascade="all, delete-orphan")
    forecasts: Mapped[list["Forecast"]] = relationship(back_populates="resource", cascade="all, delete-orphan")
    recommendations: Mapped[list["Recommendation"]] = relationship(back_populates="resource")


class ResourceMetric(Base):
    __tablename__ = "resource_metrics"
    __table_args__ = (
        UniqueConstraint("resource_id", "observed_at", name="uq_metric_resource_time"),
        Index("ix_metric_resource_time", "resource_id", "observed_at"),
        CheckConstraint("cpu_percent >= 0 AND cpu_percent <= 100"),
        CheckConstraint("memory_percent >= 0 AND memory_percent <= 100"),
        CheckConstraint("storage_percent >= 0 AND storage_percent <= 100"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    resource_id: Mapped[str] = mapped_column(ForeignKey("resources.id", ondelete="CASCADE"), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    cpu_percent: Mapped[float]
    memory_percent: Mapped[float]
    storage_percent: Mapped[float]
    network_mbps: Mapped[float]
    resource: Mapped[Resource] = relationship(back_populates="metrics")


class Forecast(Base):
    __tablename__ = "forecasts"
    __table_args__ = (UniqueConstraint("resource_id", "metric", "generated_at", "target_at", name="uq_forecast_point"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    resource_id: Mapped[str] = mapped_column(ForeignKey("resources.id", ondelete="CASCADE"), index=True)
    metric: Mapped[str] = mapped_column(String(32))
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    target_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    predicted: Mapped[float]
    lower_bound: Mapped[float]
    upper_bound: Mapped[float]
    model_name: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(24), default="available")
    resource: Mapped[Resource] = relationship(back_populates="forecasts")


class Recommendation(Base):
    __tablename__ = "recommendations"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    resource_id: Mapped[str] = mapped_column(ForeignKey("resources.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    rationale: Mapped[str] = mapped_column(Text)
    estimated_monthly_savings_cents: Mapped[int] = mapped_column(Integer, default=0)
    risk_level: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resource: Mapped[Resource] = relationship(back_populates="recommendations")
    actions: Mapped[list["OptimizationAction"]] = relationship(back_populates="recommendation")


class OptimizationAction(Base):
    __tablename__ = "optimization_actions"
    id: Mapped[int] = mapped_column(primary_key=True)
    recommendation_id: Mapped[str] = mapped_column(ForeignKey("recommendations.id"), index=True)
    requested_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    approved_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    simulated: Mapped[bool] = mapped_column(Boolean, default=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recommendation: Mapped[Recommendation] = relationship(back_populates="actions")


class AutomationPolicy(Base):
    __tablename__ = "automation_policies"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    require_approval: Mapped[bool] = mapped_column(Boolean, default=True)
    max_monthly_savings_cents: Mapped[int] = mapped_column(Integer, default=100_000)
    allowed_actions: Mapped[list] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(60), index=True)
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(80))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    user: Mapped[User | None] = relationship(back_populates="audit_events")


class AppSetting(Base):
    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
