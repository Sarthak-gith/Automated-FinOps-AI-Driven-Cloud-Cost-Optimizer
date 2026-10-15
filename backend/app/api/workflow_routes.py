from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user, get_db, require_roles
from app.db.models import (AuditEvent, AutomationPolicy, OptimizationAction,
                           Recommendation, Resource, User)

router = APIRouter(prefix="/api", tags=["approval and audit"])


class ActionRequest(BaseModel):
    note: str = Field(default="", max_length=500)


class PolicyUpdate(BaseModel):
    enabled: bool
    require_approval: Literal[True] = True
    max_monthly_savings_cents: int = Field(default=100_000, ge=0, le=100_000_000)


def _audit(db: Session, user: User, event: str, entity: str, entity_id: str, details: dict):
    db.add(AuditEvent(user_id=user.id, event_type=event, entity_type=entity,
                      entity_id=entity_id, details=details))


def _action(row: OptimizationAction):
    return {"id": row.id, "recommendation_id": row.recommendation_id,
            "action": row.action, "status": row.status, "simulated": row.simulated,
            "requested_by_id": row.requested_by_id, "approved_by_id": row.approved_by_id,
            "requested_at": row.requested_at, "decided_at": row.decided_at}


@router.post("/recommendations/{recommendation_id}/request-action")
def request_action(recommendation_id: str, body: ActionRequest,
                   db: Session = Depends(get_db),
                   user: User = Depends(require_roles("admin", "analyst"))):
    recommendation = db.get(Recommendation, recommendation_id)
    if recommendation is None:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    if recommendation.status != "pending":
        raise HTTPException(status_code=409, detail="Only pending recommendations can be requested")
    policy = db.scalar(select(AutomationPolicy).where(AutomationPolicy.name == "default"))
    if policy is None or not policy.enabled:
        raise HTTPException(status_code=409, detail="Automation is paused; new actions are disabled")
    if recommendation.kind not in (policy.allowed_actions or []):
        raise HTTPException(status_code=403, detail="This action is not allowed by the active policy")
    if recommendation.estimated_monthly_savings_cents > policy.max_monthly_savings_cents:
        raise HTTPException(status_code=403, detail="Estimated savings exceed the active policy limit")
    prior = db.scalar(select(OptimizationAction).where(
        OptimizationAction.recommendation_id == recommendation_id))
    if prior:
        raise HTTPException(status_code=409, detail="An action was already requested")
    action = OptimizationAction(recommendation_id=recommendation_id,
                                requested_by_id=user.id, action=recommendation.kind,
                                status="pending", simulated=True)
    db.add(action)
    _audit(db, user, "optimization.action_requested", "recommendation", recommendation_id,
           {"action": recommendation.kind, "simulated": True, "note": body.note})
    db.commit()
    db.refresh(action)
    return _action(action)


@router.post("/actions/{action_id}/approve")
def approve_action(action_id: int, db: Session = Depends(get_db),
                   user: User = Depends(require_roles("admin"))):
    action = db.get(OptimizationAction, action_id)
    if action is None:
        raise HTTPException(status_code=404, detail="Action not found")
    if action.status != "pending":
        raise HTTPException(status_code=409, detail="Action is not awaiting approval")
    if action.requested_by_id == user.id:
        raise HTTPException(status_code=403, detail="A different administrator must approve this action")
    action.approved_by_id = user.id
    action.status = "approved"
    action.decided_at = datetime.now(timezone.utc)
    recommendation = db.get(Recommendation, action.recommendation_id)
    recommendation.status = "approved"
    _audit(db, user, "optimization.action_approved", "action", str(action.id),
           {"simulated": True, "recommendation_id": recommendation.id})
    db.commit()
    return _action(action)


@router.post("/actions/{action_id}/reject")
def reject_action(action_id: int, body: ActionRequest,
                  db: Session = Depends(get_db),
                  user: User = Depends(require_roles("admin"))):
    action = db.get(OptimizationAction, action_id)
    if action is None:
        raise HTTPException(status_code=404, detail="Action not found")
    if action.status != "pending":
        raise HTTPException(status_code=409, detail="Action is not awaiting approval")
    action.status = "rejected"
    action.approved_by_id = user.id
    action.decided_at = datetime.now(timezone.utc)
    recommendation = db.get(Recommendation, action.recommendation_id)
    recommendation.status = "rejected"
    _audit(db, user, "optimization.action_rejected", "action", str(action.id),
           {"reason": body.note, "simulated": True})
    db.commit()
    return _action(action)


@router.post("/actions/{action_id}/execute")
def execute_action(action_id: int, db: Session = Depends(get_db),
                   user: User = Depends(require_roles("admin"))):
    action = db.get(OptimizationAction, action_id)
    if action is None:
        raise HTTPException(status_code=404, detail="Action not found")
    if action.status != "approved":
        raise HTTPException(status_code=409, detail="Only approved actions can be executed")
    policy = db.scalar(select(AutomationPolicy).where(AutomationPolicy.name == "default"))
    if policy is None or not policy.enabled:
        raise HTTPException(status_code=409, detail="Automation is paused; simulated execution is disabled")
    recommendation = db.get(Recommendation, action.recommendation_id)
    resource = db.get(Resource, recommendation.resource_id)
    if resource is None or resource.provider != "simulated" or not action.simulated:
        raise HTTPException(status_code=409, detail="Only simulated resources may be changed")
    if (action.action not in (policy.allowed_actions or []) or
            recommendation.estimated_monthly_savings_cents > policy.max_monthly_savings_cents):
        raise HTTPException(status_code=403, detail="Action no longer satisfies the active policy")
    before = {"status": resource.status, "size": resource.size, "instance_type": resource.instance_type}
    if action.action == "idle-stop":
        resource.status = "stopped"
    elif action.action == "right-size":
        resource.size = f"{resource.size}-reduced"
        resource.instance_type = f"{resource.instance_type}.reduced"
    else:
        raise HTTPException(status_code=409, detail="Unsupported simulated action")
    action.status = "executed"
    action.decided_at = datetime.now(timezone.utc)
    recommendation.status = "executed"
    _audit(db, user, "optimization.action_executed", "resource", resource.id,
           {"action": action.action, "before": before,
            "after": {"status": resource.status, "size": resource.size}, "simulated": True})
    db.commit()
    return {**_action(action), "resource_id": resource.id,
            "resource_status": resource.status, "resource_size": resource.size}


@router.get("/actions")
def actions(db: Session = Depends(get_db),
            user: User = Depends(require_roles("admin", "analyst", "viewer"))):
    rows = db.scalars(select(OptimizationAction).order_by(OptimizationAction.requested_at.desc())).all()
    return [_action(row) for row in rows]


@router.get("/policies/default")
def get_policy(db: Session = Depends(get_db),
               user: User = Depends(require_roles("admin", "analyst", "viewer"))):
    policy = db.scalar(select(AutomationPolicy).where(AutomationPolicy.name == "default"))
    if policy is None:
        raise HTTPException(status_code=404, detail="Default policy is not initialized")
    return {"name": policy.name, "enabled": policy.enabled,
            "paused": not policy.enabled, "require_approval": policy.require_approval,
            "max_monthly_savings_cents": policy.max_monthly_savings_cents,
            "allowed_actions": policy.allowed_actions}


@router.put("/policies/default")
def update_policy(body: PolicyUpdate, db: Session = Depends(get_db),
                  user: User = Depends(require_roles("admin"))):
    policy = db.scalar(select(AutomationPolicy).where(AutomationPolicy.name == "default"))
    if policy is None:
        policy = AutomationPolicy(name="default")
        db.add(policy)
    before = {"enabled": policy.enabled, "require_approval": policy.require_approval,
              "max_monthly_savings_cents": policy.max_monthly_savings_cents}
    policy.enabled = body.enabled
    policy.require_approval = body.require_approval
    policy.max_monthly_savings_cents = body.max_monthly_savings_cents
    _audit(db, user, "policy.updated", "policy", "default",
           {"before": before, "after": body.model_dump()})
    db.commit()
    return get_policy(db, user)


@router.get("/audit")
def audit_events(limit: int = 100, db: Session = Depends(get_db),
                 user: User = Depends(require_roles("admin", "analyst", "viewer"))):
    if not 1 <= limit <= 500:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 500")
    rows = db.scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(limit)).all()
    return [{"id": row.id, "user_id": row.user_id, "event_type": row.event_type,
             "entity_type": row.entity_type, "entity_id": row.entity_id,
             "details": row.details, "created_at": row.created_at}
            for row in rows]
