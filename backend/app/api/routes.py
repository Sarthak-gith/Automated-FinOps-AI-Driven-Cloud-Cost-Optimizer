from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import current_user, get_db, require_roles
from app.core.security import issue_token, verify_password
from app.db.models import AuditEvent, Resource, ResourceMetric, User

router = APIRouter(prefix="/api")


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=256)


@router.post("/auth/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    db.add(AuditEvent(user_id=user.id, event_type="auth.login", entity_type="user",
                      entity_id=str(user.id), details={"method": "local_password"}))
    db.commit()
    return {"access_token": issue_token(user.id), "token_type": "bearer",
            "user": {"id": user.id, "email": user.email, "display_name": user.display_name, "role": user.role}}


@router.get("/auth/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "email": user.email, "display_name": user.display_name, "role": user.role}


@router.get("/resources")
def resources(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Resource).order_by(Resource.name)).all()
    return [{"id": r.id, "name": r.name, "provider": r.provider, "region": r.region,
             "category": r.category, "instance_type": r.instance_type, "size": r.size,
             "status": r.status, "hourly_cost_cents": r.hourly_cost_cents,
             "estimated_monthly_cost_cents": r.hourly_cost_cents * 730 if r.status == "running" else 0,
             "labels": r.labels, "simulated": True} for r in rows]


@router.get("/resources/{resource_id}/metrics")
def resource_metrics(resource_id: str, start: datetime | None = None, end: datetime | None = None,
                     limit: int = 1000, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if db.get(Resource, resource_id) is None:
        raise HTTPException(status_code=404, detail="Resource not found")
    if limit < 1 or limit > 5000:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 5000")
    query = select(ResourceMetric).where(ResourceMetric.resource_id == resource_id)
    if start:
        query = query.where(ResourceMetric.observed_at >= start)
    if end:
        query = query.where(ResourceMetric.observed_at <= end)
    rows = db.scalars(query.order_by(ResourceMetric.observed_at.desc()).limit(limit)).all()
    return [{"observed_at": x.observed_at, "cpu_percent": x.cpu_percent,
             "memory_percent": x.memory_percent, "storage_percent": x.storage_percent,
             "network_mbps": x.network_mbps, "simulated": True} for x in reversed(rows)]


@router.get("/dashboard/summary")
def dashboard_summary(user: User = Depends(current_user), db: Session = Depends(get_db)):
    resources_count = db.scalar(select(func.count()).select_from(Resource)) or 0
    active = db.scalar(select(func.count()).select_from(Resource).where(Resource.status == "running")) or 0
    cost_cents = db.scalar(select(func.coalesce(func.sum(Resource.hourly_cost_cents), 0)).where(
        Resource.status == "running")) or 0
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    avg_cpu = db.scalar(select(func.avg(ResourceMetric.cpu_percent)).where(
        ResourceMetric.observed_at >= cutoff))
    categories = db.execute(select(Resource.category, func.count(),
                                    func.sum(Resource.hourly_cost_cents)).group_by(Resource.category)).all()
    return {"simulated": True, "resource_count": resources_count, "running_count": active,
            "hourly_cost_cents": cost_cents, "estimated_monthly_cost_cents": cost_cents * 730,
            "average_cpu_percent_24h": round(avg_cpu, 2) if avg_cpu is not None else None,
            "categories": [{"category": c, "resource_count": n, "hourly_cost_cents": cents or 0}
                           for c, n, cents in categories]}


@router.post("/simulation/seed", dependencies=[Depends(require_roles("admin"))])
def reseed_status(db: Session = Depends(get_db)):
    from app.simulation.simulator import seed_demo_data
    return seed_demo_data(db)


@router.post("/simulation/latest")
def append_latest_metrics(db: Session = Depends(get_db),
                          user: User = Depends(require_roles("admin", "analyst"))):
    from app.simulation.simulator import generate_latest_metrics
    return {"inserted_metrics": generate_latest_metrics(db), "simulated": True}
