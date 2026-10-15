from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_db
from app.core.security import hash_password
from app.db.database import Base, make_engine
from app.db.models import (AuditEvent, AutomationPolicy, Recommendation, Resource,
                           ResourceMetric, User)
from app.main import app


def make_client():
    engine = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    with TestingSession() as db:
        admin = User(email="admin@test.local", display_name="Admin", role="admin",
                     password_hash=hash_password("admin-test"))
        analyst = User(email="analyst@test.local", display_name="Analyst", role="analyst",
                       password_hash=hash_password("analyst-test"))
        db.add_all([admin, analyst])
        resource = Resource(id="sim-test-001", name="Test compute", provider="simulated",
                            region="us-east-sim-1", category="general", instance_type="sim.vm.general",
                            size="small", status="running", hourly_cost_cents=9,
                            created_at=now - timedelta(days=40), labels={"environment":"demo"})
        db.add(resource)
        db.add(Recommendation(id="rec-sim-test-001-idle-stop", resource_id=resource.id,
                              kind="idle-stop", status="pending", rationale="test estimate",
                              estimated_monthly_savings_cents=5_256, risk_level="medium"))
        for hour in range(168):
            db.add(ResourceMetric(resource_id=resource.id, observed_at=now-timedelta(hours=167-hour),
                                  cpu_percent=2, memory_percent=20, storage_percent=35, network_mbps=1))
        db.add(AutomationPolicy(name="default", enabled=True, require_approval=True,
                                max_monthly_savings_cents=100_000,
                                allowed_actions=["idle-stop", "right-size"]))
        db.commit()

    def override_db():
        with TestingSession() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    return TestClient(app), engine


def login(client, email, password):
    response = client.post("/api/auth/login", json={"email":email,"password":password})
    assert response.status_code == 200, response.text
    return {"Authorization":"Bearer "+response.json()["access_token"]}


def test_analyst_request_admin_approval_and_simulated_execution():
    client, engine = make_client()
    analyst = login(client,"analyst@test.local","analyst-test")
    request = client.post("/api/recommendations/rec-sim-test-001-idle-stop/request-action",
                          headers=analyst,json={"note":"reviewed"})
    assert request.status_code == 200, request.text
    action_id = request.json()["id"]
    assert request.json()["simulated"] is True
    assert client.post(f"/api/actions/{action_id}/execute",headers=analyst).status_code == 403

    admin = login(client,"admin@test.local","admin-test")
    approved = client.post(f"/api/actions/{action_id}/approve",headers=admin)
    assert approved.status_code == 200, approved.text
    executed = client.post(f"/api/actions/{action_id}/execute",headers=admin)
    assert executed.status_code == 200, executed.text
    assert executed.json()["resource_status"] == "stopped"
    assert client.post(f"/api/actions/{action_id}/execute",headers=admin).status_code == 409

    with Session(engine) as db:
        assert db.get(Resource,"sim-test-001").status == "stopped"
        assert db.query(AuditEvent).count() >= 4
    app.dependency_overrides.clear()
    engine.dispose()


def test_paused_policy_and_csv_report_are_enforced():
    client, engine = make_client()
    analyst = login(client,"analyst@test.local","analyst-test")
    policy = client.post("/api/recommendations/rec-sim-test-001-idle-stop/request-action",
                         headers=analyst,json={})
    assert policy.status_code == 200
    admin = login(client,"admin@test.local","admin-test")
    invalid_policy=client.put("/api/policies/default",headers=admin,json={"enabled":True,"require_approval":False,"max_monthly_savings_cents":100000})
    assert invalid_policy.status_code == 422
    action_id=policy.json()["id"]
    assert client.post(f"/api/actions/{action_id}/approve",headers=admin).status_code == 200
    changed=client.put("/api/policies/default",headers=admin,json={"enabled":False,"require_approval":True,"max_monthly_savings_cents":100000})
    assert changed.status_code == 200
    assert client.post(f"/api/actions/{action_id}/execute",headers=admin).status_code == 409
    report=client.get("/api/reports/cost-optimization.csv",headers=analyst)
    assert report.status_code == 200
    assert "text/csv" in report.headers["content-type"]
    assert "sim-test-001" in report.text
    assert client.get("/api/reports/summary",headers=analyst).json()["simulated"] is True
    app.dependency_overrides.clear()
    engine.dispose()


def test_admin_can_regenerate_simulation_without_losing_accounts_or_policy():
    client, engine = make_client()
    admin = login(client,"admin@test.local","admin-test")
    result = client.post("/api/simulation/regenerate",headers=admin)
    assert result.status_code == 200, result.text
    assert result.json()["resources"] == 20
    assert result.json()["simulated"] is True
    assert client.get("/api/auth/me",headers=admin).json()["email"] == "admin@test.local"
    policy = client.get("/api/policies/default",headers=admin)
    assert policy.status_code == 200 and policy.json()["enabled"] is True
    assert len(client.get("/api/resources",headers=admin).json()) == 20
    app.dependency_overrides.clear()
    engine.dispose()
