import random
import logging
from config import Config

logger = logging.getLogger(__name__)

# Cache: link → file_id  (avoids repeated channel fetches for the same GIF)
_gif_cache: dict = {}

# ── Rich text fallbacks shown when a GIF can't be sent ───────────────────────
_RUN_TEXT = {
    1: "1️⃣ **SINGLE!** — Smart cricket, easy run taken!",
    2: "2️⃣ **TWO!** — Great running between the wickets!",
    3: "3️⃣ **THREE!** — Excellent running, three earned!",
    4: "🟢 **FOUR!** — Races to the boundary, timed perfectly!",
    5: "5️⃣ **FIVE!** — Rare sight, brilliant effort field!",
    6: "🔥 **SIX!** — SMASHED INTO THE STANDS! What a shot! 🏟️",
}

async def get_file_id(client, link: str):
    """Fetch animation/video file_id from a t.me channel post link."""
    if link in _gif_cache:
        return _gif_cache[link]
    try:
        parts    = link.rstrip("/").split("/")
        username = parts[-2]
        msg_id   = int(parts[-1])
        msg      = await client.get_messages(f"@{username}", msg_id)
        if msg and msg.animation:
            fid = msg.animation.file_id
        elif msg and msg.video:
            fid = msg.video.file_id
        elif msg and msg.document:
            fid = msg.document.file_id
        else:
            return None
        _gif_cache[link] = fid
        return fid
    except Exception as e:
        logger.debug(f"GIF fetch skipped for {link}: {e}")
        return None

async def send_gif(client, chat_id: int, link: str, caption: str = "") -> bool:
    """Try to send a GIF. Returns True on success, False on failure."""
    fid = await get_file_id(client, link)
    if not fid:
        return False
    for send in (client.send_animation, client.send_video):
        try:
            await send(chat_id, fid, caption=caption)
            return True
        except Exception:
            continue
    return False

# ── Public helpers called by solo.py / team_gameplay.py ──────────────────────

async def send_run_gif(client, chat_id: int, runs: int, batter_name: str):
    run_map = {
        1: Config.GIF_1_RUN, 2: Config.GIF_2_RUN, 3: Config.GIF_3_RUN,
        4: Config.GIF_4_RUN, 5: Config.GIF_5_RUN, 6: Config.GIF_6_RUN,
    }
    caption = f"{_RUN_TEXT.get(runs, f'**{runs} runs**')} — **{batter_name}**"
    link    = run_map.get(runs)
    if link:
        sent = await send_gif(client, chat_id, link, caption)
        if sent:
            return
    # Fallback: text only
    await client.send_message(chat_id, caption)

async def send_wicket_gif(client, chat_id: int, batter_name: str):
    caption = (
        f"❌ **WICKET!** — **{batter_name}** is gone!\n"
        f"🚶 Walks back to the pavilion... clean delivery, no answer!"
    )
    sent = await send_gif(client, chat_id, Config.GIF_WICKET, caption)
    if sent:
        await send_gif(client, chat_id, Config.GIF_WALKBACK)
    else:
        await client.send_message(chat_id, caption)

async def send_bowling_prompt_gif(client, chat_id: int):
    link = random.choice(Config.GIF_BOWLING)
    sent = await send_gif(client, chat_id, link)
    if not sent:
        await client.send_message(chat_id, "🎳 **Bowler runs in...**")

async def send_match_start_gif(client, chat_id: int):
    sent = await send_gif(client, chat_id, Config.GIF_MATCH_START)
    if not sent:
        await client.send_message(
            chat_id,
            "🏟️ **The crowd roars! The match begins!** 🎉\n🏏 Let the cricket begin!"
        )

async def send_trophy_gif(client, chat_id: int, caption: str = ""):
    sent = await send_gif(client, chat_id, Config.GIF_TROPHY, caption)
    if not sent and caption:
        await client.send_message(chat_id, f"🏆🏆🏆\n{caption}")
