from __future__ import annotations

import asyncio
import os

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message

from app.conversation import ConversationService
from app.db import SessionLocal


dp = Dispatcher()


@dp.message(CommandStart())
async def start(message: Message) -> None:
    await message.answer(
        "Buonasera. Sono il concierge di Artusi. Dimmi per quante persone, "
        "che giorno e a che ora vuoi prenotare."
    )


@dp.message(F.text)
async def handle_text(message: Message) -> None:
    if not message.text:
        return
    async with SessionLocal() as session:
        service = ConversationService(session)
        result = await service.handle(f"tg:{message.chat.id}", message.text)

    await message.answer(result.reply)
    if result.booking:
        await message.answer(f"Codice prenotazione: {result.booking.id}")


async def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit(
            "Falta TELEGRAM_BOT_TOKEN. Crea un bot con @BotFather y expórtalo en el entorno."
        )
    bot = Bot(token=token)
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
