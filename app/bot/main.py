import asyncio
import logging
from aiogram import Bot, Dispatcher
from app.config import settings
from app.bot.handlers import commands, submission, review

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("autoshorts.bot")


def build_dispatcher() -> Dispatcher:
    """Build and wire aiogram Dispatcher with all handler routers."""
    dp = Dispatcher()
    dp.include_router(commands.router)
    dp.include_router(submission.router)
    dp.include_router(review.router)
    return dp


async def main():
    """Bot entrypoint for standalone execution."""
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not configured. Telegram Bot cannot start.")
        return

    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    dp = build_dispatcher()

    logger.info("AutoShorts Telegram Bot starting polling...")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())

