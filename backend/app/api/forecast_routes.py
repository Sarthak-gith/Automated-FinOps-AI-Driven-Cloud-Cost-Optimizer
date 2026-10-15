from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.db.models import User
from app.forecasting.service import generate_forecast, latest_forecasts

router = APIRouter(prefix="/api/forecasts", tags=["forecasts"])


@router.get("")
def list_forecasts(resource_id: str | None = None, db: Session = Depends(get_db),
                   user: User = Depends(require_roles("admin", "analyst", "viewer"))):
    return latest_forecasts(db, resource_id)


@router.post("/generate")
def generate(resource_id: str | None = None,
             horizon_hours: int = Query(default=168, ge=1, le=168),
             force: bool = False, db: Session = Depends(get_db),
             user: User = Depends(require_roles("admin", "analyst"))):
    from sqlalchemy import select
    from app.db.models import Resource

    ids = [resource_id] if resource_id else db.scalars(select(Resource.id).order_by(Resource.id)).all()
    results = []
    for rid in ids:
        try:
            result = generate_forecast(db, rid, horizon_hours, force)
        except ValueError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        results.append({"resource_id": result.resource_id, "status": result.status,
                        "model": result.model, "generated_at": result.generated_at,
                        "points": result.points, "mae": result.mae, "rmse": result.rmse,
                        "message": result.message, "simulated": True})
    return {"results": results}
