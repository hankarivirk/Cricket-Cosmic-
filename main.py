import asyncio, logging
from pyrogram import Client
from pyrogram.types import BotCommand
from config import Config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

Config.check()
from database import verify_connection

app = Client(
    "CricCrazeBot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN,
    plugins=dict(root="plugins")
)

COMMANDS = [
    BotCommand("start",       "Match shuru karo / Game mode choose karo"),
    BotCommand("help",        "All commands aur help dekho"),
    BotCommand("join_solo",   "Solo match join karo"),
    BotCommand("leave_solo",  "Solo match chhodo"),
    BotCommand("solo_score",  "Solo live scorecard"),
    BotCommand("start_solo",  "Force start solo (Admin)"),
    BotCommand("end_solo",    "Solo match end karo (Admin)"),
    BotCommand("create_teams","Team joining kholo (Host)"),
    BotCommand("join_a",      "Team A join karo"),
    BotCommand("join_b",      "Team B join karo"),
    BotCommand("members_list","Teams aur players dekho"),
    BotCommand("choose_caps", "Captains choose karo (Host)"),
    BotCommand("set_overs",   "Overs set karo (Captain)"),
    BotCommand("batting",     "Batter choose karo (Captain)"),
    BotCommand("bowling",     "Bowler choose karo (Captain)"),
    BotCommand("score",       "Team live scorecard"),
    BotCommand("end_match",   "Match end karo (Admin)"),
    BotCommand("tournament",  "Tournament shuru karo"),
    BotCommand("t_score",     "Tournament standings"),
    BotCommand("t_end",       "Tournament end karo (Host/Admin)"),
    BotCommand("stats",       "Apni stats dekho"),
    BotCommand("leaderboard", "Top players list"),
    BotCommand("spamfree",    "Spam-free toggle (Admin)"),
]

async def main():
    logger.info("Checking database...")
    await verify_connection()
    logger.info("✅ Database OK")

    async with app:
        me = await app.get_me()

        import utils.state as state
        state.bot_name     = me.first_name or state.bot_name
        state.bot_username = me.username

        # Register "/" command menu visible in all group chats
        try:
            from pyrogram.types import BotCommandScopeAllGroupChats, BotCommandScopeDefault
            await app.set_bot_commands(COMMANDS, scope=BotCommandScopeAllGroupChats())
            await app.set_bot_commands(COMMANDS, scope=BotCommandScopeDefault())
            logger.info("✅ Bot commands registered")
        except Exception as e:
            logger.warning(f"set_bot_commands failed (non-critical): {e}")

        logger.info(f"✅ @{me.username} — {me.first_name} is LIVE!")
        await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
