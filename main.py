import asyncio
import logging
from pyrogram import Client
from config import Config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# Validate required environment variables before anything else runs, so a
# missing/blank setting fails immediately with a clear message instead of
# crashing deep inside some unrelated import (which is what happened before:
# an unset MONGO_URI crashed the whole process the instant `database` was
# imported by a plugin, with the bot never getting the chance to even log in
# to Telegram — every command silently doing nothing).
Config.check()

from database import verify_connection  # noqa: E402  (import after Config.check())

plugins = dict(root="plugins")

app = Client(
    "CricCrazeBot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN,
    plugins=plugins
)

async def main():
    logger.info("Checking database connection...")
    await verify_connection()
    logger.info("✅ Database connection OK.")

    async with app:
        me = await app.get_me()

        # Detect the bot's real display name straight from the token instead
        # of hardcoding a brand string — every reply that mentions the bot's
        # name will automatically match whatever name is set in @BotFather.
        import utils.state as state
        state.bot_name = me.first_name or state.bot_name
        state.bot_username = me.username

        logger.info(f"✅ @{me.username} — {me.first_name} is LIVE!")
        await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
