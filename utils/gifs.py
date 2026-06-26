import random, logging
from config import Config
logger = logging.getLogger(__name__)
_gif_cache: dict = {}

async def _get_fid(client, link: str):
    if not link: return None
    if link in _gif_cache: return _gif_cache[link]
    try:
        parts = link.rstrip("/").split("/")
        msg = await client.get_messages(f"@{parts[-2]}", int(parts[-1]))
        fid = (msg.animation or msg.video or msg.document)
        fid = fid.file_id if fid else None
        if fid: _gif_cache[link] = fid
        return fid
    except Exception as e:
        logger.debug(f"GIF skip {link}: {e}")
        return None

async def _send(client, chat_id, link, caption="", reply_markup=None):
    fid = await _get_fid(client, link)
    if not fid: return False
    try:
        await client.send_animation(chat_id, fid, caption=caption, reply_markup=reply_markup)
        return True
    except Exception:
        try:
            await client.send_video(chat_id, fid, caption=caption, reply_markup=reply_markup)
            return True
        except Exception:
            return False

# ── Public helpers ────────────────────────────────────────────────────────────

async def send_run_gif(client, chat_id: int, runs: int, batter_id: int, batter_name: str):
    captions = {
        0: f"⚫ **Dot Ball!** — No run.",
        1: f"1️⃣ **Single!** — Smart running! [{batter_name}](tg://user?id={batter_id})",
        2: f"2️⃣ **TWO!** — Great running! [{batter_name}](tg://user?id={batter_id})",
        3: f"3️⃣ **THREE!** — Brilliant effort! [{batter_name}](tg://user?id={batter_id})",
        4: f"🟢 **FOUR!** — Races to the boundary! [{batter_name}](tg://user?id={batter_id})",
        5: f"5️⃣ **FIVE!** — Rare sight! [{batter_name}](tg://user?id={batter_id})",
        6: f"🔥 **SIX!** — SMASHED INTO THE STANDS! [{batter_name}](tg://user?id={batter_id}) 💥",
    }
    links = {
        1: Config.GIF_1_RUN, 2: Config.GIF_2_RUN, 3: Config.GIF_3_RUN,
        4: Config.GIF_4_RUN, 5: Config.GIF_5_RUN, 6: Config.GIF_6_RUN,
    }
    cap  = captions.get(runs, f"**{runs} runs!**")
    link = links.get(runs)
    if link:
        sent = await _send(client, chat_id, link, caption=cap)
        if sent: return
    await client.send_message(chat_id, cap)

async def send_wicket_gif(client, chat_id: int, batter_id: int, batter_name: str):
    cap = (
        f"❌ **WICKET!** — [{batter_name}](tg://user?id={batter_id}) is OUT!\n"
        f"🚶 Walks back to the pavilion..."
    )
    sent = await _send(client, chat_id, Config.GIF_WICKET, caption=cap)
    if not sent:
        await client.send_message(chat_id, cap)

async def send_bowling_prompt_gif(client, chat_id: int, prompt_text: str, reply_markup=None):
    """Send bowling GIF with prompt text as caption + DM button inline."""
    link = random.choice(Config.GIF_BOWLING)
    sent = await _send(client, chat_id, link, caption=prompt_text, reply_markup=reply_markup)
    if not sent:
        await client.send_message(chat_id, prompt_text, reply_markup=reply_markup)

async def send_match_start_gif(client, chat_id: int):
    sent = await _send(client, chat_id, Config.GIF_MATCH_START,
                       caption="🏟️ **The crowd roars — the match begins!** 🎉")
    if not sent:
        await client.send_message(chat_id, "🏟️ **The crowd roars — the match begins!** 🎉")

async def send_trophy_gif(client, chat_id: int, caption: str = ""):
    sent = await _send(client, chat_id, Config.GIF_TROPHY, caption=caption)
    if not sent and caption:
        await client.send_message(chat_id, f"🏆🏆🏆\n{caption}")
