import csv
import io
import logging
import os
import secrets
import sqlite3
import time
from collections import defaultdict, deque
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from openai import AsyncOpenAI
from gemini_client import generate_reply
from email_notifications import send_lead_notice
from pydantic import BaseModel, EmailStr, Field

logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parent
PROD = os.getenv("APP_ENV", "development").lower() == "production"
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./peachflow.db")
SESSION_SECRET = os.getenv("SESSION_SECRET", "")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
PUBLIC_URL = os.getenv("PUBLIC_URL", "").rstrip("/")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
if PROD and (not SESSION_SECRET or not ADMIN_PASSWORD or not DATABASE_URL.startswith(("postgres://", "postgresql://"))):
    raise RuntimeError("Production requires SESSION_SECRET, ADMIN_PASSWORD and a persistent PostgreSQL DATABASE_URL")
if not SESSION_SECRET:
    SESSION_SECRET = secrets.token_urlsafe(48)
serializer = URLSafeTimedSerializer(SESSION_SECRET, salt="peachflow-admin-v1")
app = FastAPI(title="COKIT Digital", docs_url=None, redoc_url=None)
limits = defaultdict(deque)

def using_pg():
    return DATABASE_URL.startswith(("postgres://", "postgresql://"))

@contextmanager
def dbconn():
    if using_pg():
        import psycopg2
        from psycopg2.extras import RealDictCursor
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=10, cursor_factory=RealDictCursor, sslmode="require")
    else:
        raw = DATABASE_URL.replace("sqlite:///", "", 1)
        location = ROOT / raw if not os.path.isabs(raw) else Path(raw)
        location.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(location, timeout=15)
        conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def execute(conn, sql, params=(), fetch=False):
    if using_pg():
        sql = sql.replace("?", "%s")
    cur = conn.cursor()
    cur.execute(sql, params)
    rows = [dict(x) for x in cur.fetchall()] if fetch else None
    cur.close()
    return rows

def init_db():
    with dbconn() as conn:
        execute(conn, """CREATE TABLE IF NOT EXISTS leads (
          id TEXT PRIMARY KEY, name TEXT NOT NULL, business TEXT NOT NULL,
          email TEXT NOT NULL, interest TEXT NOT NULL, message TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'New', notes TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL)""")
        execute(conn, """CREATE TABLE IF NOT EXISTS chats (
          id TEXT PRIMARY KEY, message TEXT NOT NULL, reply TEXT NOT NULL,
          mode TEXT NOT NULL, created_at TEXT NOT NULL)""")
init_db()

def stamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def throttle(request, kind, cap):
    ip = request.client.host if request.client else "unknown"
    key = (ip, kind)
    queue = limits[key]
    now = time.monotonic()
    while queue and now - queue[0] > 60:
        queue.popleft()
    if len(queue) >= cap:
        raise HTTPException(429, "Too many requests; try again shortly")
    queue.append(now)

def origin_check(request):
    if not PROD:
        return
    origin = request.headers.get("origin")
    host = PUBLIC_URL or str(request.base_url).rstrip("/")
    if origin and origin.rstrip("/") != host:
        raise HTTPException(403, "Origin mismatch")

def require_admin(request):
    token = request.cookies.get("pf_admin", "")
    try:
        if serializer.loads(token, max_age=8*3600) != "admin":
            raise HTTPException(401, "Unauthorized")
    except (BadSignature, SignatureExpired):
        raise HTTPException(401, "Sign in required")

class Lead(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    business: str = Field(min_length=2, max_length=120)
    email: EmailStr
    interest: str = Field(min_length=2, max_length=120)
    message: str = Field(min_length=5, max_length=2000)

class Chat(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    history: list[dict] = Field(default_factory=list, max_length=8)

class Login(BaseModel):
    password: str = Field(min_length=1, max_length=512)

class LeadUpdate(BaseModel):
    status: str
    notes: str = Field(default="", max_length=3000)

CATALOG = """You are COKIT Digital's helpful, concise customer assistant. You serve Georgia, USA businesses remotely. Answer accurately; do not invent guarantees, contact details or completed integrations. Prices in USD are introductory estimates, third-party/AI/hosting fees additional. Launch Website $199 setup + $19/mo (up to 3 pages, forms, basic SEO, analytics). Growth Automation $399 setup + $49/mo (lead capture, CRM, scheduling, one automated workflow, review requests). Integration Pro from $899 setup + $99/mo (two supported integrations and two workflows). AI chatbot $99-$249 setup, usage extra; additional app integration $99-$299; reputation management $29-$59/mo; SEO/content $79-$199/mo; custom dashboard $149-$399 setup. Other services: AI customer acquisition from $49/mo, customer support from $29/mo, unified operations dashboard from $49/mo, CRM, appointment booking, automated reviews, inventory/accounting integrations and marketing. Invite clients to submit a consultation request, never request payment credentials, and do not promise an exact turnaround or savings."""

def fallback(text, history=None):
    """Topic-aware, non-generative assistance when the AI provider is unavailable."""
    import re
    history = history or []
    message = text.lower().strip()
    context = " ".join(
        str(turn.get("content", ""))[:300].lower()
        for turn in history[-4:] if isinstance(turn, dict) and turn.get("role") == "user"
    )
    topics = {
        "dashboard": ("dashboard", "dashboards", "analytics", "reporting", "reports", "kpi", "metrics", "insights"),
        "automation": ("automate", "automation", "workflow", "follow-up", "reminder", "repetitive", "scheduling", "appointment"),
        "website": ("website", "web design", "webpage", "site", "landing page", "ecommerce", "online store"),
        "integration": ("integration", "integrate", "connect", "crm", "api", "sync", "inventory", "accounting"),
        "chatbot": ("chatbot", "chat bot", "ai assistant", "customer support bot", "virtual agent"),
        "marketing": ("seo", "marketing", "review", "reputation", "traffic", "leads", "customers")
    }
    def matches(words, content):
        return any(re.search(r"(?<![a-z])" + re.escape(word) + r"(?![a-z])", content) for word in words)
    topic = next((name for name, words in topics.items() if matches(words, message)), None)
    if topic is None and matches(("yes", "sure", "okay", "ok", "tell me more", "how", "what", "cost", "price", "much", "it"), message):
        topic = next((name for name, words in topics.items() if matches(words, context)), None)
    answers = {
        "dashboard": ("Absolutely — COKIT Digital builds custom dashboards to bring your most useful numbers into one place. "
                      "We can track leads, sales, booking activity, operations, or marketing KPIs, depending on which systems you use. "
                      "Custom dashboard setup typically starts at $149–$399, with final pricing based on integrations and scope. "
                      "What would you like your dashboard to track, and where is that data stored?"),
        "automation": ("We can automate lead capture, CRM updates, appointment scheduling, reminders, customer follow-ups and review requests. "
                       "Our Growth Automation package starts at $399 setup plus $49/month for a scoped workflow; third-party costs are extra. "
                       "Which task does your team repeat most often?"),
        "website": ("We design responsive websites that help visitors understand your business and contact you. "
                    "Our Launch Website package starts at $199 setup plus $19/month for up to three pages, forms, SEO basics and analytics. "
                    "Is this a new website or a redesign, and what type of business is it for?"),
        "integration": ("We connect business tools so information can move between them without repeated manual entry. "
                        "Examples include CRM, appointments, inventory, accounting and reporting. "
                        "Integration Pro starts from $899 setup plus $99/month for two supported connections and workflows. "
                        "Which platforms do you need connected?"),
        "chatbot": ("We can build a customer-facing AI chat assistant to answer common questions, capture inquiries and direct complex requests to your team. "
                    "Initial setup is typically $99–$249; AI usage is additional. "
                    "Would it be for customer support, leads, bookings, or something else?"),
        "marketing": ("We help businesses improve online visibility and customer trust through SEO support, review workflows and smarter lead follow-up. "
                      "Reputation services start at $29–$59/month, with separate SEO or content options. "
                      "Is your main goal more traffic, more inquiries, or better reviews?")
    }
    if topic:
        if matches(("price", "cost", "how much", "monthly", "quote", "rate"), message):
            return answers[topic]
        return answers[topic]
    if matches(("price", "cost", "how much", "package", "rates"), message):
        return ("Our Launch Website starts at $199 setup + $19/month, Growth Automation at $399 + $49/month, "
                "and Integration Pro from $899 + $99/month. Custom dashboards start at $149–$399 setup. "
                "Third-party and AI usage fees are additional. Which service would you like a quote for?")
    if matches(("hello", "hey", "hi", "good morning", "good evening"), message):
        return "Hello! I can help you with websites, automation, dashboards, integrations and AI assistants. What are you looking to build?"
    return ("I can help you explore COKIT Digital services. Tell me a little more about your goal — "
            "for example, 'I need a sales dashboard' or 'I want to automate customer follow-ups'. "
            "You can also submit your requirements at /vision to request a tailored consultation.")

@app.get("/api/health")
def health():
    return {"status": "ok", "ai_configured": bool(GEMINI_API_KEY or OPENAI_API_KEY)}

@app.post("/api/leads", status_code=201)
def add_lead(body: Lead, request: Request, background_tasks: BackgroundTasks):
    throttle(request, "leads", 5)
    origin_check(request)
    lead_id = secrets.token_hex(12)
    with dbconn() as conn:
        execute(conn, "INSERT INTO leads(id,name,business,email,interest,message,status,notes,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (lead_id, body.name.strip(), body.business.strip(), str(body.email), body.interest.strip(),
             body.message.strip(), "New", "", stamp()))
    background_tasks.add_task(send_lead_notice, {"name": body.name.strip(), "business": body.business.strip(),
        "email": str(body.email), "interest": body.interest.strip(), "message": body.message.strip(),
        "reference": lead_id})
    return {"received": True, "reference": lead_id}

@app.post("/api/chat")
async def chat(body: Chat, request: Request):
    throttle(request, "chat", 12)
    origin_check(request)
    reply = fallback(body.message, body.history)
    mode = "faq"
    if GEMINI_API_KEY:
        try:
            reply = await generate_reply(body.message, body.history, CATALOG)
            mode = "gemini"
        except Exception:
            logger.exception("Gemini chatbot generation failed")
            mode = "fallback"
    elif OPENAI_API_KEY:
        try:
            conversation = []
            for x in body.history[-8:]:
                if isinstance(x, dict) and x.get("role") in ("user", "assistant") and isinstance(x.get("content"), str):
                    conversation.append({"role": x["role"], "content": x["content"][:1000]})
            conversation.append({"role": "user", "content": body.message})
            result = await AsyncOpenAI(api_key=OPENAI_API_KEY, timeout=18, max_retries=1).chat.completions.create(
                model=OPENAI_MODEL, messages=[{"role":"system","content":CATALOG}, *conversation],
                max_tokens=240)
            reply = result.choices[0].message.content or reply
            mode = "ai"
        except Exception:
            logger.exception("Chatbot generation failed")
            mode = "fallback"
    try:
        with dbconn() as conn:
            execute(conn, "INSERT INTO chats(id,message,reply,mode,created_at) VALUES (?,?,?,?,?)",
                (secrets.token_hex(12), body.message, reply, mode, stamp()))
    except Exception:
        logger.exception("Chat log persistence failed; continuing to serve chatbot response")
    return {"reply": reply, "mode": mode}

@app.post("/api/admin/login")
def login(body: Login, request: Request):
    throttle(request, "login", 8)
    origin_check(request)
    if not ADMIN_PASSWORD or not secrets.compare_digest(body.password.encode(), ADMIN_PASSWORD.encode()):
        raise HTTPException(401, "Invalid credentials")
    response = JSONResponse({"ok": True})
    response.set_cookie("pf_admin", serializer.dumps("admin"), httponly=True, secure=PROD,
                        samesite="strict", max_age=8*3600, path="/")
    return response

@app.post("/api/admin/logout")
def logout(request: Request):
    origin_check(request)
    response = JSONResponse({"ok": True})
    response.delete_cookie("pf_admin", path="/")
    return response

@app.get("/api/admin/overview")
def overview(request: Request):
    require_admin(request)
    with dbconn() as conn:
        leads = execute(conn, "SELECT * FROM leads ORDER BY created_at DESC LIMIT 500", fetch=True)
        chats = execute(conn, "SELECT * FROM chats ORDER BY created_at DESC LIMIT 100", fetch=True)
    return {"leads": leads, "chats": chats, "metrics": {
        "total_leads": len(leads), "new_leads": sum(x["status"]=="New" for x in leads),
        "won_leads": sum(x["status"]=="Won" for x in leads), "chat_messages": len(chats)}}

@app.patch("/api/admin/leads/{lead_id}")
def update_lead(lead_id: str, body: LeadUpdate, request: Request):
    require_admin(request)
    origin_check(request)
    if body.status not in ("New", "Contacted", "Qualified", "Won", "Lost"):
        raise HTTPException(400, "Invalid status")
    with dbconn() as conn:
        existing = execute(conn, "SELECT id FROM leads WHERE id=?", (lead_id,), fetch=True)
        if not existing:
            raise HTTPException(404, "Lead not found")
        execute(conn, "UPDATE leads SET status=?,notes=? WHERE id=?",
                (body.status, body.notes, lead_id))
    return {"updated": True}

@app.get("/api/admin/export")
def export_leads(request: Request):
    require_admin(request)
    with dbconn() as conn:
        leads = execute(conn, "SELECT * FROM leads ORDER BY created_at DESC", fetch=True)
    buf = io.StringIO()
    writer = csv.writer(buf)
    keys = ["id", "name", "business", "email", "interest", "message", "status", "notes", "created_at"]
    writer.writerow(keys)
    for lead in leads:
        writer.writerow(["'" + str(lead[k]) if str(lead[k]).startswith(("=", "+", "-", "@")) else lead[k] for k in keys])
    return Response(content=buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="peachflow-leads.csv"'})

@app.get("/")
def homepage():
    return FileResponse(ROOT / "index.html")

@app.get("/admin")
def admin():
    return FileResponse(ROOT / "admin.html")

@app.get("/services")
@app.get("/services/")
def services_page():
    return FileResponse(ROOT / "services.html")

@app.get("/vision")
@app.get("/vision/")
def vision_page():
    return FileResponse(ROOT / "vision.html")

@app.get("/site.css")
def site_styles():
    return FileResponse(ROOT / "site.css", media_type="text/css")

@app.get("/site.js")
def site_script():
    return FileResponse(ROOT / "site.js", media_type="application/javascript")
