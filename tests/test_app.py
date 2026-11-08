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

def test_cokit_branding_scrolling_header_and_restored_assistant():
    for route in ("/","/services","/vision"):
        response=client.get(route)
        assert response.status_code==200
        assert "COKIT Digital" in response.text
        assert "Peachflow Digital" not in response.text
    assert "COKIT" in client.get("/admin").text
    css=client.get("/site.css")
    assert css.status_code==200
    assert ".site-nav{position:relative" in css.text
    assert ".site-nav{position:sticky" not in css.text
    assert ".assistant-pane" in css.text
    js=client.get("/site.js")
    assert js.status_code==200
    assert "COKIT AI Assistant" in js.text
    assert "fetch('/api/chat'" in js.text
    result=client.post("/api/chat",json={"message":"What services do you offer?","history":[]})
    assert result.status_code==200
    assert result.json().get("reply")

def test_fallback_handles_dashboard_topic_and_followups(monkeypatch):
    monkeypatch.setattr(app, "GEMINI_API_KEY", "")
    monkeypatch.setattr(app, "OPENAI_API_KEY", "")
    first=client.post("/api/chat",json={"message":"dashboard","history":[]})
    assert first.status_code==200
    assert first.json()["mode"]=="faq"
    assert "dashboard" in first.json()["reply"].lower()
    assert "track" in first.json()["reply"].lower()
    assert "Welcome to" not in first.json()["reply"]
    history=[{"role":"user","content":"dashboard"},{"role":"assistant","content":first.json()["reply"]}]
    follow=client.post("/api/chat",json={"message":"how much does it cost","history":history})
    assert follow.status_code==200
    assert "$149" in follow.json()["reply"]
    workflow=client.post("/api/chat",json={"message":"I need automated reminders","history":[]})
    assert workflow.status_code==200
    assert "automation" in workflow.json()["reply"].lower()
    monkeypatch.undo()

def test_failed_gemini_uses_contextual_fallback(monkeypatch):
    async def provider_failure(message, history, instructions):
        raise RuntimeError("Provider unavailable")
    monkeypatch.setattr(app,"GEMINI_API_KEY","test-provider-key")
    monkeypatch.setattr(app,"generate_reply",provider_failure)
    response=client.post("/api/chat",json={"message":"dashboard","history":[]})
    assert response.status_code==200
    assert response.json()["mode"]=="fallback"
    assert "dashboard" in response.json()["reply"].lower()
    assert "Welcome to" not in response.json()["reply"]

def test_request_handoff_links_directly_to_real_form(monkeypatch):
    async def no_provider(*args):
        raise AssertionError("Direct handoff must not depend on provider")
    monkeypatch.setattr(app,"GEMINI_API_KEY","test-key")
    monkeypatch.setattr(app,"generate_reply",no_provider)
    for message in ("where can I submit my request", "How do I send a project request?", "where is the consultation form?"):
        result=client.post("/api/chat",json={"message":message,"history":[]})
        assert result.status_code==200, result.text
        assert result.json()["mode"]=="handoff"
        assert "/vision" in result.json()["reply"]
        assert "submit" in result.json()["reply"].lower()
    assert 'assistant-project-link' in client.get("/site.js").text
    assert 'formLink.href=\'/vision\'' in client.get("/site.js").text

def test_email_in_chat_does_not_get_misidentified_or_claim_submission(monkeypatch):
    monkeypatch.setattr(app,"GEMINI_API_KEY","")
    result=client.post("/api/chat",json={
        "message":"my email is collinsthuo254@gmail.com",
        "history":[{"role":"user","content":"I want a dashboard for my hotel"}]})
    assert result.status_code==200
    assert result.json()["mode"]=="handoff"
    answer=result.json()["reply"]
    assert "/vision" in answer
    assert "has not submitted" in answer
    assert "Collinsthuo254" not in answer
    assert "collinsthuo254@gmail.com" not in answer

def test_catalog_includes_concise_link_and_no_implied_submission():
    catalog=app.CATALOG.lower()
    assert "not submitted" in catalog or "never claim to have officially submitted" in catalog
    assert "/vision" in catalog
    assert "do not infer a person's name from their email address" in catalog

def test_chatbot_vision_form_and_dashboard_integration(monkeypatch):
    """The chat intake uses the same persisted lead endpoint as the standalone form."""
    app.limits.clear()  # Each integration scenario should have an independent rate-limit window.
    script=client.get("/site.js").text
    for snippet in ("assistantVisionForm","Submit your vision in chat","name=\"name\"",
                    "name=\"business\"","name=\"email\"","name=\"interest\"",
                    "name=\"message\"","/api/leads","assistantVisionStatus",
                    "avConsent","data.reference"):
        assert snippet in script
    assert "visionForm.reportValidity()" in script
    assert "response.ok" in script
    assert "Request received!" in script
    assert ".assistant-vision-panel[hidden]{display:none}" in client.get("/site.css").text
    monkeypatch.setattr(app,"GEMINI_API_KEY","")
    response=client.post("/api/chat",json={"message":"Where can I submit my request?","history":[]})
    assert response.status_code==200
    assert "Submit your vision in chat" in response.json()["reply"]
    lead=client.post("/api/leads",json={
        "name":"Alex Test","business":"Hotel Demo Ltd","email":"alex-test@example.com",
        "interest":"Custom Dashboard",
        "message":"Build a dashboard for room bookings, sales, occupancy and payments."})
    assert lead.status_code==201,lead.text
    ref=lead.json()["reference"]
    assert ref
    login=client.post("/api/admin/login",json={"password":"test-admin-password"})
    assert login.status_code==200
    overview=client.get("/api/admin/overview")
    assert overview.status_code==200
    found=[item for item in overview.json()["leads"] if item["id"]==ref]
    assert found and found[0]["business"]=="Hotel Demo Ltd"
    assert "occupancy" in found[0]["message"]
    assert found[0]["status"]=="New"
