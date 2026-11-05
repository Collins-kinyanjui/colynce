# PeachFlow Digital

A brown, ivory and gold glass-UI digital agency website serving Georgia, USA.

## Included
- Responsive marketing site with affordable service packages and a simulated lead-to-CRM demo.
- Real website AI chat powered by the Google Gemini API when `GEMINI_API_KEY` is configured (OpenAI is an optional secondary provider) (FAQ fallback otherwise).
- Consultation form persisted in SQLite locally or PostgreSQL in production.
- Cookie-authenticated admin dashboard for leads, status/notes, CSV export, chat logs and metrics.
- Render deployment blueprint. **GitHub stores source code; it does not run this Python server.**

## Deploy without local installation
1. Go to [Render](https://dashboard.render.com/), connect this GitHub repository, and choose **New > Blueprint**.
2. Use a Supabase PostgreSQL connection URI as the private Render **DATABASE_URL**. Replace the password placeholder with the actual database password in Render only (URL-encode reserved characters). Supabase pooler port 6543 is supported; use the correct Supabase-provided connection settings. The app deliberately refuses an ephemeral SQLite database in production.
3. Set `ADMIN_PASSWORD` to a strong, unique password and `GEMINI_API_KEY` to a valid Google AI Studio Gemini key; these must be **secret environment variables, never committed to Git**. `SESSION_SECRET` is auto-generated in the Blueprint.
4. Deploy, open the Render site URL, and open `/admin` to sign in. Use the same site for the chatbot and consultation form.
5. Set `PUBLIC_URL` to the deployed site origin (e.g. `https://peachflow-digital.onrender.com`) in the Render environment to enforce admin request origin checks.
6. Confirm persistent leads, live AI response mode, and admin access before sharing publicly.

## Environment
```
APP_ENV=development
DATABASE_URL=sqlite:///./peachflow.db
ADMIN_PASSWORD=your-long-random-admin-password
SESSION_SECRET=replace-with-random-64-character-string
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash
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
- Do not paste Gemini keys or database passwords into chat or commit them. Rotate any exposed API key before deployment.
- No payment processing, email delivery, actual CRM synchronization, or customer portal has been implemented.
- Simple process-local rate limiting is an MVP measure; add managed edge/WAF rate limiting and monitoring before higher volume.
- Use a verified company email/address and replace placeholders before outreach.

## Services and introductory USD pricing
Launch Website: $199 setup + $19/month; Growth Automation: $399 setup + $49/month; Integration Pro: from $899 setup + $99/month. AI chat setup from $99; additional integrations from $99; reputation management from $29/month; SEO/content from $79/month; custom dashboards from $149 setup; AI lead acquisition from $49/month; AI support from $29/month; unified operations dashboards from $49/month. Scope/usage constraints apply.

## Email notifications for new leads
Consultation requests are stored in the database first; then an email is sent in a background task via Resend. Set `RESEND_API_KEY`, `EMAIL_FROM` (e.g. `PeachFlow <hello@your-verified-domain.example>`), and `NOTIFY_EMAIL` to the private destination address in the Render dashboard. Verify your sender domain in Resend before sending to arbitrary inboxes. Do not commit keys or private contact addresses to GitHub. Failed email notifications are logged, and leads stay accessible at `/admin`. There is no automatic retry queue in this MVP; use admin as the source of truth.

## Troubleshooting chatbot
- `GET /api/health` displays whether an AI credential was configured, but cannot verify validity.
- If Gemini fails, the app logs a server-side exception and responds with pricing/FAQ fallback.
- If saving a chat log fails, a valid chatbot answer is still returned instead of a 500 error.
- Verify `GEMINI_API_KEY`, Gemini model availability/quota, and `DATABASE_URL` in Render. Never paste secrets into public logs.
- `PUBLIC_URL` must exactly match the scheme and hostname of the public website, without a trailing slash; mismatch can reject POST requests.
