from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.db.models import User
from app.optimization.service import generate_recommendations, list_recommendations

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])


def _serialize(row):
    return {"id": row.id, "resource_id": row.resource_id, "kind": row.kind,
            "status": row.status, "rationale": row.rationale,
            "estimated_monthly_savings_cents": row.estimated_monthly_savings_cents,
            "risk_level": row.risk_level, "created_at": row.created_at,
            "simulated": True, "estimate": True}


@router.get("")
def recommendations(status: str | None = None, db: Session = Depends(get_db),
                    user: User = Depends(require_roles("admin", "analyst", "viewer"))):
    return [_serialize(row) for row in list_recommendations(db, status)]


@router.post("/generate")
def generate(lookback_days: int = Query(default=7, ge=1, le=30),
             db: Session = Depends(get_db),
             user: User = Depends(require_roles("admin", "analyst"))):
    try:
        rows = generate_recommendations(db, lookback_days)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {"recommendations": [_serialize(row) for row in rows], "simulated": True}
