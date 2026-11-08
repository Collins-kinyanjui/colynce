import importlib
import os
from fastapi.testclient import TestClient

os.environ["APP_ENV"] = "development"
os.environ["ADMIN_PASSWORD"] = "test-admin-password"
os.environ["SESSION_SECRET"] = "test-secret-not-for-production"
os.environ["DATABASE_URL"] = "sqlite:///./test_peachflow.db"
os.environ.pop("OPENAI_API_KEY", None)
os.environ.pop("GEMINI_API_KEY", None)
os.environ.pop("RESEND_API_KEY", None)
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

def test_gemini_mode_without_external_request(monkeypatch):
    async def fake_gemini(message, history, instructions):
        assert message == "Tell me about your services"
        return "We offer websites and business automation."
    monkeypatch.setattr(app, "GEMINI_API_KEY", "test-only-configured")
    monkeypatch.setattr(app, "generate_reply", fake_gemini)
    response = client.post("/api/chat", json={"message": "Tell me about your services", "history": []})
    assert response.status_code == 200
    assert response.json()["mode"] == "gemini"
    assert "business automation" in response.json()["reply"]

def test_email_delivery_is_queued_without_public_credentials(monkeypatch):
    captured = []
    async def send_notice(lead):
        captured.append(lead)
    monkeypatch.setattr(app, "send_lead_notice", send_notice)
    result = client.post("/api/leads", json={
        "name": "Morgan Lee", "business": "Maple Home Services",
        "email": "morgan@example.com", "interest": "Launch Website",
        "message": "Please contact me about a website."
    })
    assert result.status_code == 201
    assert captured and captured[0]["email"] == "morgan@example.com"
    assert captured[0]["reference"] == result.json()["reference"]

def test_chat_response_survives_logging_database_failure(monkeypatch):
    original = app.dbconn
    from contextlib import contextmanager
    @contextmanager
    def failing_db():
        raise RuntimeError("temporary database outage")
        yield
    monkeypatch.setattr(app, "dbconn", failing_db)
    monkeypatch.setattr(app, "GEMINI_API_KEY", "")
    response = client.post("/api/chat", json={"message": "What does the website cost?", "history": []})
    assert response.status_code == 200
    assert response.json()["mode"] == "faq"
    monkeypatch.setattr(app, "dbconn", original)

def test_three_page_navigation_and_assets():
    home=client.get("/")
    services=client.get("/services")
    vision=client.get("/vision")
    assert all(response.status_code==200 for response in [home,services,vision])
    assert "Make your business" in home.text
    assert "Automation workflow" in home.text
    assert "Growth Automation" in services.text
    assert "Build something remarkable." in vision.text
    assert 'id="visionForm"' in vision.text
    assert 'name="interest"' in vision.text
    assert client.get("/site.css").status_code==200
    assert client.get("/site.js").status_code==200
    assert "prefers-reduced-motion" in client.get("/site.css").text
