"""FastAPI entry point for the local simulated FinOps application."""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.api.routes import router
from app.api.forecast_routes import router as forecast_router
from app.api.optimization_routes import router as optimization_router
from app.api.workflow_routes import router as workflow_router
from app.core.security import hash_password
from app.db.database import SessionLocal, initialize_database
from app.db.models import AutomationPolicy, User
from app.simulation.simulator import seed_demo_data

app = FastAPI(title="Automated FinOps API", version="0.1.0",
              description="Local demo using simulated cloud resources and telemetry.")
app.add_middleware(CORSMiddleware, allow_origins=os.getenv(
    "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(","),
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(router)
app.include_router(forecast_router)
app.include_router(optimization_router)
app.include_router(workflow_router)


@app.on_event("startup")
def startup() -> None:
    initialize_database()
    with SessionLocal() as db:
        if db.scalar(select(User.id).limit(1)) is None:
            demo_users = [
                ("admin@finops.local", "FinOps Admin", "admin", "Admin123!"),
                ("analyst@finops.local", "FinOps Analyst", "analyst", "Analyst123!"),
                ("viewer@finops.local", "FinOps Viewer", "viewer", "Viewer123!"),
            ]
            for email, name, role, password in demo_users:
                db.add(User(email=email, display_name=name, role=role,
                            password_hash=hash_password(os.getenv(
                                f"DEMO_{role.upper()}_PASSWORD", password))))
            db.commit()
        if db.scalar(select(AutomationPolicy.id).where(AutomationPolicy.name == "default")) is None:
            db.add(AutomationPolicy(name="default", enabled=True, require_approval=True,
                                    max_monthly_savings_cents=100_000,
                                    allowed_actions=["idle-stop", "right-size"]))
            db.commit()
        seed_demo_data(db, resource_count=int(os.getenv("SIM_RESOURCE_COUNT", "20")),
                       history_days=int(os.getenv("SIM_HISTORY_DAYS", "30")))


@app.get("/health")
def health():
    return {"status": "ok", "mode": "simulated", "cloud_api_enabled": False}
