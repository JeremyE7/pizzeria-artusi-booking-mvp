# 60-second demo script

Record with Loom, OBS or the browser. Keep it under 90 seconds. The point is to
show a **working flow**, not to read the README.

## Before recording

- `docker compose up -d`
- Open the chat page at a clean state.
- Have `/admin` open in a second tab.
- Use a fake name: `Mario Rossi`.
- Have the terminal ready with `pytest -q` if you want to show the tests.

## Script

1. **0:00 — Show the pizzeria**
   “This is Pizzería Artusi, a booking assistant that looks like a classic
   pizzeria game. The guest talks to Artusi, the waiter.”

2. **0:08 — Ask in Spanish**
   Click the suggestion: `Una mesa para 4 personas mañana a las 20:30`.
   “It understands Spanish, Italian and English.”

3. **0:18 — Give the name**
   Type `Mario Rossi`.
   “It asks only for what is missing.”

4. **0:25 — Confirm**
   Type `sí`.
   “The confirmation is idempotent: if the guest sends it twice, it returns the
   same receipt. The booking checks table capacity and overlap.”

5. **0:38 — Show the receipt**
   Point at the code, table and time.
   “This code is the key the kitchen uses.”

6. **0:45 — Show the kitchen**
   Switch to `/admin`.
   “Every confirmed booking becomes a comanda on the kitchen rail.”

7. **0:55 — Show the engineering**
   “FastAPI, async SQLAlchemy, PostgreSQL, 20 tests, Docker. The LLM and
   Telegram adapters are ready; the demo uses deterministic mocks so it runs
   without keys.”

8. **1:05 — Close**
   “I can plug in the real Telegram token and OpenRouter key, or scope the pilot
   with you.”

## Don’t show

- The Tailscale IP or internal admin password.
- Real guest data.
- A long terminal log or code scroll.
