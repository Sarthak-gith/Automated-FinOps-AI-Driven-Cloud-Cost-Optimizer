"""Server-generated CSV and JSON reports for the simulated environment."""

import csv
from io import StringIO

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.db.models import Recommendation, Resource, User

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/summary")
def report_summary(db: Session = Depends(get_db),
                   user: User = Depends(require_roles("admin", "analyst", "viewer"))):
    resources = db.scalars(select(Resource)).all()
    recommendations = db.scalars(select(Recommendation)).all()
    monthly_cost = sum(r.hourly_cost_cents * 730 for r in resources if r.status == "running")
    pending_savings = sum(r.estimated_monthly_savings_cents for r in recommendations
                          if r.status == "pending")
    return {"simulated": True, "resource_count": len(resources),
            "running_count": sum(r.status == "running" for r in resources),
            "monthly_cost_cents": monthly_cost,
            "pending_estimated_savings_cents": pending_savings,
            "recommendations_by_status": dict(db.execute(
                select(Recommendation.status, func.count()).group_by(Recommendation.status)).all())}


@router.get("/cost-optimization.csv")
def cost_optimization_csv(db: Session = Depends(get_db),
                          user: User = Depends(require_roles("admin", "analyst", "viewer"))):
    output = StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow(["record_type", "resource_id", "name", "category_or_kind", "status",
                     "hourly_cost_cents", "monthly_cost_or_savings_cents", "risk", "rationale", "simulated"])
    resources = db.scalars(select(Resource).order_by(Resource.id)).all()
    for resource in resources:
        monthly = resource.hourly_cost_cents * 730 if resource.status == "running" else 0
        writer.writerow(["resource", resource.id, resource.name, resource.category, resource.status,
                         resource.hourly_cost_cents, monthly, "", "", "true"])
    recommendations = db.scalars(select(Recommendation).order_by(Recommendation.created_at.desc())).all()
    for item in recommendations:
        writer.writerow(["recommendation", item.resource_id, "", item.kind, item.status, "",
                         item.estimated_monthly_savings_cents, item.risk_level, item.rationale, "true"])
    output.seek(0)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": "attachment; filename=automated-finops-simulated-report.csv",
                                      "Cache-Control": "no-store"})
