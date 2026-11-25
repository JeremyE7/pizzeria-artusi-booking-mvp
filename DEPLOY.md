# Deploy the public demo

The app is a Docker service plus PostgreSQL. The repo includes a Render
Blueprint (`render.yaml`), but the same image works on Railway, Fly.io or any
VPS with Docker.

## Recommended: Render

1. Push the repo to GitHub.
2. In the Render dashboard: **New → Blueprint** and connect the repo.
3. Render reads `render.yaml` and creates:
   - `pizzeria-artusi` (Docker web service)
   - `pizzeria-artusi-db` (PostgreSQL)
4. When prompted, set `DEMO_BASIC_AUTH` to a value like
   `demo:choose-a-long-password`. This protects `/admin`,
   `/api/bookings` and `/api/reminders`; `/` and `/chat` stay public.
5. Deploy. The public URL will look like
   `https://pizzeria-artusi.onrender.com`.
6. Check:
   - `/health`
   - `/` (chat)
   - `/admin` with the Basic Auth credentials
7. In the GitHub repo settings, add the live URL as the website.

The free Render PostgreSQL instance expires after 30 days. For a longer-lived
client demo, upgrade the database or use Neon/Supabase and set `DATABASE_URL`
manually.

## Railway alternative

1. New project → **Deploy from GitHub**.
2. Add a PostgreSQL database.
3. Set `DATABASE_URL` to the database connection string.
4. Set `DEMO_BASIC_AUTH` to `demo:<password>`.
5. Deploy from the Dockerfile.

Railway usually provides a `postgresql://` URL; `app/config.py` normalises it
to `postgresql+psycopg://`.

## Fly.io alternative

```bash
fly launch --dockerfile Dockerfile
fly postgres create
fly postgres attach <postgres-app-name>
fly secrets set DEMO_BASIC_AUTH='demo:<password>'
fly deploy
```

## Pre-public checklist

- [ ] `DEMO_BASIC_AUTH` is set and is not `demo:demo`.
- [ ] The public URL uses HTTPS.
- [ ] `/admin` returns `401` without credentials.
- [ ] The provider's database backups or expiry policy are understood.
- [ ] The demo data is fake; no real guest names or phone numbers are stored.
- [ ] The Tailscale URL is not used as the client-facing demo URL.
