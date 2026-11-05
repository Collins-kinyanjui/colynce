# PeachFlow Digital

A brown, ivory and gold glass-UI digital agency website serving Georgia, USA.

## Included
- Responsive marketing site with affordable service packages and a simulated lead-to-CRM demo.
- Real website AI chat powered by the OpenAI Responses API when `OPENAI_API_KEY` is configured (FAQ fallback otherwise).
- Consultation form persisted in SQLite locally or PostgreSQL in production.
- Cookie-authenticated admin dashboard for leads, status/notes, CSV export, chat logs and metrics.
- Render deployment blueprint. **GitHub stores source code; it does not run this Python server.**

## Deploy without local installation
1. Go to [Render](https://dashboard.render.com/), connect this GitHub repository, and choose **New > Blueprint**.
2. Create a managed PostgreSQL database separately on Render or another provider and supply its **DATABASE_URL** (PostgreSQL preferred). The app deliberately refuses an ephemeral SQLite database in production.
3. Set `ADMIN_PASSWORD` to a strong, unique password and `OPENAI_API_KEY` to a funded OpenAI API key; these must be **secret environment variables, never committed to Git**. `SESSION_SECRET` is auto-generated in the Blueprint.
4. Deploy, open the Render site URL, and open `/admin` to sign in. Use the same site for the chatbot and consultation form.
5. Set `PUBLIC_URL` to the deployed site origin (e.g. `https://peachflow-digital.onrender.com`) in the Render environment to enforce admin request origin checks.
6. Confirm persistent leads, live AI response mode, and admin access before sharing publicly.

## Environment
```
APP_ENV=development
DATABASE_URL=sqlite:///./peachflow.db
ADMIN_PASSWORD=your-long-random-admin-password
SESSION_SECRET=replace-with-random-64-character-string
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
PUBLIC_URL=
```

## Local (optional)
```bash
python -m pip install -r requirements.txt
uvicorn app:app --reload
```
Then visit http://localhost:8000 and http://localhost:8000/admin .

## Security & operations
- Configure secure HTTPS and a persistent PostgreSQL database for production.
- Leads and conversations contain customer data; establish a privacy policy, access controls, retention schedule, and backup plan before going live.
- Chat is not a binding quote; listed prices are introductory USD rates, with hosting, AI usage and third-party tools extra.
- No payment processing, email delivery, actual CRM synchronization, or customer portal has been implemented.
- Simple process-local rate limiting is an MVP measure; add managed edge/WAF rate limiting and monitoring before higher volume.
- Use a verified company email/address and replace placeholders before outreach.

## Services and introductory USD pricing
Launch Website: $199 setup + $19/month; Growth Automation: $399 setup + $49/month; Integration Pro: from $899 setup + $99/month. AI chat setup from $99; additional integrations from $99; reputation management from $29/month; SEO/content from $79/month; custom dashboards from $149 setup; AI lead acquisition from $49/month; AI support from $29/month; unified operations dashboards from $49/month. Scope/usage constraints apply.
