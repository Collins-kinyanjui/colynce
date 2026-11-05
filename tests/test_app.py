import importlib
import os
from fastapi.testclient import TestClient

os.environ["APP_ENV"] = "development"
os.environ["ADMIN_PASSWORD"] = "test-admin-password"
os.environ["SESSION_SECRET"] = "test-secret-not-for-production"
os.environ["DATABASE_URL"] = "sqlite:///./test_peachflow.db"
os.environ.pop("OPENAI_API_KEY", None)
app = importlib.import_module("app")
client = TestClient(app.app)

def test_health_and_home():
    assert client.get("/api/health").status_code == 200
    assert client.get("/").status_code == 200
    assert client.get("/admin").status_code == 200

def test_lead_admin_flow():
    assert client.get("/api/admin/overview").status_code == 401
    result = client.post("/api/leads", json={
        "name":"Jordan Taylor","business":"Peach Test Cleaning",
        "email":"jordan@example.com","interest":"Growth Automation",
        "message":"Please automate our quote follow-ups."
    })
    assert result.status_code == 201, result.text
    assert client.post("/api/admin/login",json={"password":"wrong"}).status_code == 401
    assert client.post("/api/admin/login",json={"password":"test-admin-password"}).status_code == 200
    overview = client.get("/api/admin/overview")
    assert overview.status_code == 200
    assert len(overview.json()["leads"]) >= 1
    lead_id = result.json()["reference"]
    assert client.patch("/api/admin/leads/"+lead_id,json={"status":"Qualified","notes":"Call tomorrow"}).status_code == 200
    assert "Qualified" in client.get("/api/admin/export").text
    assert client.post("/api/admin/logout").status_code == 200
    assert client.get("/api/admin/overview").status_code == 401

def test_chat_faq():
    r = client.post("/api/chat",json={"message":"How much is the website package?","history":[]})
    assert r.status_code == 200
    assert "$199" in r.json()["reply"]
    assert r.json()["mode"] == "faq"
