# Freelancer pitch kit

The public URL and GitHub repo are live. Fill in `[NAME]` only.

- **Live demo:** https://pizzeria-artusi.onrender.com
- **Code:** https://github.com/JeremyE7/pizzeria-artusi-booking-mvp

The Render free instance can take 30–60 seconds on the first request after
inactivity. Open it once before sending the message so it is warm.

## One-liner

> I built a working restaurant booking assistant with Python async, PostgreSQL,
> an LLM-ready parser, a Telegram adapter and a kitchen comanda panel. Here is
> the live demo: https://pizzeria-artusi.onrender.com · code:
> https://github.com/JeremyE7/pizzeria-artusi-booking-mvp

## English message for the Freelancer project thread

Hi [NAME],

I built a working reference implementation of the booking assistant described
in your project, not just a mockup:

**Live demo:** https://pizzeria-artusi.onrender.com
**Code:** https://github.com/JeremyE7/pizzeria-artusi-booking-mvp

It covers the core slice:

- Python async with FastAPI + SQLAlchemy and PostgreSQL.
- A multilingual intent layer (Spanish / Italian / English) with an OpenRouter
  adapter and a deterministic fallback.
- Availability by table and capacity, with overlapping bookings blocked.
- Idempotent confirmations: retrying the same confirmation returns the same
  receipt instead of creating a second booking.
- A Telegram adapter (aiogram) ready to plug in a bot token.
- A kitchen panel where each confirmed booking appears as a comanda.
- 19 automated tests and a Docker + PostgreSQL setup.

The demo currently runs with a mocked LLM and mocked Telegram so it needs no
keys; switching to OpenRouter or a real bot is configuration plus the adapter
already in the repo. WhatsApp/voice are not in this MVP yet.

I’d be glad to walk you through it in 10 minutes and scope the pilot city with
you.

Best,
Jeremy

## Spanish message for Workana

Hola [NOMBRE]:

Armé una implementación funcional del asistente de reservas que describís, no
solo un mockup:

**Demo:** https://pizzeria-artusi.onrender.com
**Código:** https://github.com/JeremyE7/pizzeria-artusi-booking-mvp

Incluye:

- Python async con FastAPI + SQLAlchemy y PostgreSQL.
- Parser multilingüe (español / italiano / inglés) con adapter de OpenRouter y
  fallback determinístico.
- Disponibilidad por mesa y capacidad, sin doble reserva.
- Confirmación idempotente: si se reintenta, devuelve la misma comanda.
- Adapter de Telegram con aiogram listo para conectar un token.
- Panel de cocina con las reservas como comandas.
- 20 tests automáticos y Docker + PostgreSQL.

La demo funciona con LLM y Telegram simulados; pasar a OpenRouter o a un bot
real es configuración más el adapter que ya está. WhatsApp/voz todavía no está
en este MVP.

Si te sirve, te muestro el flujo en 10 minutos y ajustamos el alcance del
piloto.

Saludos,
Jeremy

## Short version for a bid update

> Working reference implementation, not a mockup: Python async + PostgreSQL,
> LLM-ready parser, Telegram adapter, idempotent bookings, kitchen panel,
> 20 tests. Live demo: https://pizzeria-artusi.onrender.com · code:
> https://github.com/JeremyE7/pizzeria-artusi-booking-mvp

## How to update the Freelancer bid

1. Open the project’s **Messages** thread and send the short version with the
   live demo and GitHub links. This works even if the original bid text cannot
   be edited.
2. If Freelancer offers **Edit bid** for that project, add the same links to the
   bid body and keep the price/timeline unchanged.
3. Do not paste the admin password in the public bid. Send it in the private
   message only if the client asks for the panel.
4. Attach one screenshot (the chat with the receipt) so the client sees the
   product before clicking.

## Honest scope note

The project proves the booking engine, the AI-ready layer and the operator
view. It does not yet prove real WhatsApp/voice or a production live LLM.
Say that explicitly; it builds more trust than claiming the full spec.
