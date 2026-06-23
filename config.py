import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # ── Bot Credentials ──────────────────────────────
    API_ID    = int(os.environ.get("API_ID", 0))
    API_HASH  = os.environ.get("API_HASH", "")
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

    # ── Admin ─────────────────────────────────────────
    ADMIN_ID  = int(os.environ.get("ADMIN_ID", 0))

    # ── Database ──────────────────────────────────────
    MONGO_URI = os.environ.get("MONGO_URI", "")

    # ── Links ─────────────────────────────────────────
    PLAYZONE_LINK = os.environ.get("PLAYZONE_LINK", "https://t.me/")
    SUPPORT_LINK  = os.environ.get("SUPPORT_LINK",  "https://t.me/")

    # ── GIF Assets ────────────────────────────────────
    # Set these to your channel: https://t.me/YOUR_CHANNEL/MSG_ID
    # The bot must be a member of the channel (or channel must be public).
    GIF_1_RUN    = os.environ.get("GIF_1_RUN",    "https://t.me/assetshaibkl/2")
    GIF_2_RUN    = os.environ.get("GIF_2_RUN",    "https://t.me/assetshaibkl/4")
    GIF_3_RUN    = os.environ.get("GIF_3_RUN",    "https://t.me/assetshaibkl/6")
    GIF_4_RUN    = os.environ.get("GIF_4_RUN",    "https://t.me/assetshaibkl/7")
    GIF_5_RUN    = os.environ.get("GIF_5_RUN",    "https://t.me/assetshaibkl/9")
    GIF_6_RUN    = os.environ.get("GIF_6_RUN",    "https://t.me/assetshaibkl/11")
    GIF_WICKET   = os.environ.get("GIF_WICKET",   "https://t.me/assetshaibkl/12")
    GIF_WALKBACK = os.environ.get("GIF_WALKBACK", "https://t.me/assetshaibkl/13")
    GIF_BOWLING  = [
        os.environ.get("GIF_BOWLING_1", "https://t.me/assetshaibkl/15"),
        os.environ.get("GIF_BOWLING_2", "https://t.me/assetshaibkl/16"),
        os.environ.get("GIF_BOWLING_3", "https://t.me/assetshaibkl/17"),
    ]
    GIF_TROPHY      = os.environ.get("GIF_TROPHY",      "https://t.me/assetshaibkl/22")
    GIF_MATCH_START = os.environ.get("GIF_MATCH_START", "https://t.me/assetshaibkl/23")

    # ── Game Settings ─────────────────────────────────
    JOIN_TIMEOUT       = 120   # seconds to wait for players to join
    BOWL_TIMEOUT       = 60    # seconds for bowler to send number in DM
    BAT_TIMEOUT        = 60    # seconds for batter to type number in group
    MIN_PLAYERS_SOLO   = 2
    MAX_PLAYERS_SOLO   = 20
    MAX_ZEROS_PER_OVER = 2     # max dot balls (0s) a batter can send per over

    @classmethod
    def check(cls):
        missing = [
            name for name in ("API_ID", "API_HASH", "BOT_TOKEN", "ADMIN_ID", "MONGO_URI")
            if not getattr(cls, name)
        ]
        if missing:
            raise SystemExit(
                f"❌ Missing required env var(s): {', '.join(missing)}\n"
                f"   Set them in Railway Variables or your .env file."
            )
