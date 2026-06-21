from motor.motor_asyncio import AsyncIOMotorClient
from config import Config

# Config.check() (called at the very top of main.py) already guarantees
# MONGO_URI is set before this module is ever imported, so we don't have to
# guard against an empty string here. We do still add explicit timeouts so
# that a wrong/unreachable URI (e.g. IP not whitelisted on Atlas — the most
# common Railway deploy mistake) fails fast with a clear error instead of
# hanging the bot silently.
client = AsyncIOMotorClient(
    Config.MONGO_URI,
    serverSelectionTimeoutMS=12500,
    connectTimeoutMS=8000,
    socketTimeoutMS=15000,
)
db = client["CricCrazeBot"]

# Collections
users_col      = db["users"]
stats_col      = db["stats"]
matches_col    = db["matches"]
tournament_col = db["tournaments"]
groups_col     = db["groups"]


async def verify_connection() -> None:
    """Ping the database once at startup. Raises SystemExit with a clear,
    readable message if it can't be reached, instead of letting the bot
    crash-loop forever on a connection it will never be able to make."""
    try:
        await client.admin.command("ping")
    except Exception as e:
        raise SystemExit(
            f"❌ Could not connect to MongoDB: {type(e).__name__}: {e}\n"
            f"   Check MONGO_URI, and make sure your deployment's IP is "
            f"allow-listed in MongoDB Atlas (Network Access → 0.0.0.0/0 for Railway)."
        ) from e
