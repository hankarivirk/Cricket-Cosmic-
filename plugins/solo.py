import asyncio, random
from pyrogram import Client, filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from config import Config
from utils.state import solo_matches, SoloMatch, PlayerScore, GamePhase
import utils.state as state
from utils.ui import solo_scorecard, solo_result_card, bat_prompt, bowl_prompt, bowl_keyboard, dot_ball_msg, century_msg, mention
from utils.gifs import send_run_gif, send_wicket_gif, send_bowling_prompt_gif, send_match_start_gif, send_trophy_gif
from database.stats import update_batting_stats, update_bowling_stats, update_motm

ADMIN_S = (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)

async def _is_admin(client, chat_id, uid):
    try:
        return (await client.get_chat_member(chat_id, uid)).status in ADMIN_S
    except: return False

# ── Mode menu (called from start.py) ─────────────────────────────────────────
async def show_mode_menu(client, message):
    cid = message.chat.id
    if cid in solo_matches or cid in state.team_matches:
        return await message.reply("⚠️ Ek match already chal raha hai is group mein!")
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🧍 Solo Match", callback_data=f"mode_solo_{message.from_user.id}"),
        InlineKeyboardButton("👥 Team Match", callback_data=f"mode_team_{message.from_user.id}"),
    ]])
    await message.reply("🏏 **Choose Your Battle!**\n\n🧍 **Solo** — Every man for himself.\n👥 **Team** — Two sides, one champion.", reply_markup=kb)

@Client.on_callback_query(filters.regex("^mode_solo_"))
async def cb_mode_solo(client, cb: CallbackQuery):
    hid = int(cb.data.split("_")[-1])
    if cb.from_user.id != hid: return await cb.answer("🔒 Sirf starter choose kar sakta hai!", show_alert=True)
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("3 Balls", callback_data=f"soloovers_3_{hid}"),
        InlineKeyboardButton("6 Balls", callback_data=f"soloovers_6_{hid}"),
    ]])
    await cb.message.edit_text("🧍 **Solo Match**\n\nHar player ko kitni balls milegi?", reply_markup=kb)
    await cb.answer()

@Client.on_callback_query(filters.regex("^soloovers_"))
async def cb_solo_overs(client, cb: CallbackQuery):
    _, overs, hid = cb.data.split("_"); overs, hid = int(overs), int(hid)
    if cb.from_user.id != hid: return await cb.answer("🔒 Sirf starter choose kar sakta hai!", show_alert=True)
    cid = cb.message.chat.id
    match = SoloMatch(chat_id=cid, host_id=hid, overs=overs, phase=GamePhase.JOINING)
    solo_matches[cid] = match
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🙋 Join Match", callback_data=f"joinsolo_{cid}")]])
    msg = await cb.message.edit_text(
        f"🧍 **SOLO MATCH STARTING!**\n\n🎯 {overs} Balls/Player\n👥 Min 2 — Max 20 players\n\nTap below or `/join_solo`",
        reply_markup=kb)
    match.join_msg_id = msg.id
    await cb.answer()
    asyncio.create_task(_join_timer(client, cid))

async def _join_timer(client, cid):
    await asyncio.sleep(Config.JOIN_TIMEOUT)
    m = solo_matches.get(cid)
    if m and m.phase == GamePhase.JOINING:
        if len(m.players) >= Config.MIN_PLAYERS_SOLO: await _begin(client, cid)
        else:
            await client.send_message(cid, "⚠️ **Match Cancelled!** Not enough players.")
            solo_matches.pop(cid, None)

@Client.on_callback_query(filters.regex("^joinsolo_"))
async def cb_join_solo(client, cb: CallbackQuery):
    await _do_join(client, int(cb.data.split("_")[1]), cb.from_user, cb)

@Client.on_message(filters.command("join_solo") & filters.group)
async def cmd_join_solo(client, msg: Message):
    await _do_join(client, msg.chat.id, msg.from_user, msg)

async def _do_join(client, cid, user, ctx):
    m = solo_matches.get(cid); is_cb = isinstance(ctx, CallbackQuery)
    def rep(t): return ctx.answer(t, show_alert=True) if is_cb else ctx.reply(t)
    if not m or m.phase != GamePhase.JOINING: return await rep("⚠️ No joining window open!")
    if user.id in m.players: return await rep("✅ Already joined!")
    if len(m.players) >= Config.MAX_PLAYERS_SOLO: return await rep("⚠️ Match full!")
    m.players[user.id] = PlayerScore(user_id=user.id, full_name=user.full_name)
    m.order.append(user.id)
    names = "\n".join(f"  {i+1}. {p.full_name}" for i, p in enumerate(m.players.values()))
    try:
        await client.edit_message_text(cid, m.join_msg_id,
            f"🧍 **SOLO — JOINING** ({len(m.players)} players)\n\n{names}\n\nTap to join!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🙋 Join", callback_data=f"joinsolo_{cid}")]]))
    except: pass
    if is_cb: await ctx.answer("✅ Joined!")
    else: await ctx.reply(f"✅ {mention(user.id, user.full_name)} joined!")

@Client.on_message(filters.command("leave_solo") & filters.group)
async def cmd_leave(client, msg: Message):
    m = solo_matches.get(msg.chat.id)
    if not m or m.phase != GamePhase.JOINING: return await msg.reply("⚠️ No joining window!")
    uid = msg.from_user.id
    if uid not in m.players: return await msg.reply("⚠️ Tu joined nahi hai!")
    del m.players[uid]; m.order.remove(uid)
    await msg.reply(f"👋 {mention(uid, msg.from_user.full_name)} left.")

@Client.on_message(filters.command("solo_list") & filters.group)
async def cmd_solo_list(client, msg: Message):
    m = solo_matches.get(msg.chat.id)
    if not m: return await msg.reply("⚠️ No active solo match!")
    names = "\n".join(f"  {i+1}. {p.full_name}" for i, p in enumerate(m.players.values()))
    await msg.reply(f"👥 **Players ({len(m.players)}):**\n{names or 'None'}")

@Client.on_message(filters.command("start_solo") & filters.group)
async def cmd_force_start(client, msg: Message):
    if not await _is_admin(client, msg.chat.id, msg.from_user.id): return await msg.reply("🔒 Admins only!")
    m = solo_matches.get(msg.chat.id)
    if not m or m.phase != GamePhase.JOINING: return await msg.reply("⚠️ No joining window!")
    if len(m.players) < Config.MIN_PLAYERS_SOLO: return await msg.reply(f"⚠️ Min {Config.MIN_PLAYERS_SOLO} players needed!")
    await _begin(client, msg.chat.id)

@Client.on_message(filters.command("end_solo") & filters.group)
async def cmd_end_solo(client, msg: Message):
    if not await _is_admin(client, msg.chat.id, msg.from_user.id): return await msg.reply("🔒 Admins only!")
    m = solo_matches.pop(msg.chat.id, None)
    if m: state.pending_bowl.pop(m.current_bowler_id, None); await msg.reply("🛑 Solo match ended!")
    else: await msg.reply("⚠️ No active match!")

@Client.on_message(filters.command("solo_score") & filters.group)
async def cmd_solo_score(client, msg: Message):
    m = solo_matches.get(msg.chat.id)
    if not m: return await msg.reply("⚠️ No active match!")
    await msg.reply(solo_scorecard([vars(p) for p in m.players.values()], m.overs))

@Client.on_message(filters.command("extend_solo") & filters.group)
async def cmd_extend(client, msg: Message):
    if not await _is_admin(client, msg.chat.id, msg.from_user.id): return await msg.reply("🔒 Admins only!")
    m = solo_matches.get(msg.chat.id)
    if not m or m.phase != GamePhase.JOINING: return await msg.reply("⚠️ No joining window!")
    await msg.reply("⏱️ +30 seconds added!")
    asyncio.create_task(_ext_timer(client, msg.chat.id))

async def _ext_timer(client, cid):
    await asyncio.sleep(30)
    m = solo_matches.get(cid)
    if m and m.phase == GamePhase.JOINING:
        if len(m.players) >= Config.MIN_PLAYERS_SOLO: await _begin(client, cid)
        else:
            await client.send_message(cid, "⚠️ Match Cancelled! Not enough players.")
            solo_matches.pop(cid, None)

# ── Core gameplay ─────────────────────────────────────────────────────────────

async def _begin(client, cid):
    m = solo_matches[cid]
    m.phase = GamePhase.BOWLING
    random.shuffle(m.order)
    await send_match_start_gif(client, cid)
    await client.send_message(cid,
        f"🏏 **MATCH STARTED!**\n\n"
        f"👥 {len(m.players)} players  |  🎯 {m.overs} balls each\n\n"
        f"🔥 Let the game begin!")
    await _next_ball(client, cid)

async def _next_ball(client, cid):
    m = solo_matches.get(cid)
    if not m: return
    remaining = [uid for uid in m.order if not m.players[uid].is_out]
    if not remaining: return await _finish(client, cid)

    batter_id = remaining[0]
    batter    = m.players[batter_id]

    # Same bowler for the full over; rotate only when batter changes
    candidates = [uid for uid in m.order if uid != batter_id]
    if not candidates:
        await client.send_message(cid, "⚠️ Not enough players to continue!"); solo_matches.pop(cid, None); return

    bowler_id = candidates[m.current_bowler_idx % len(candidates)]
    bowler    = m.players[bowler_id]

    m.bowl_number       += 1
    m.phase              = GamePhase.BOWLING
    m.current_batter_id  = batter_id
    m.current_bowler_id  = bowler_id
    m.turn_id           += 1
    turn = m.turn_id

    state.pending_bowl[bowler_id] = {"chat_id": cid, "kind": "solo", "turn_id": turn}

    txt = bowl_prompt(bowler_id, bowler.full_name, m.bowl_number, m.overs)
    await send_bowling_prompt_gif(client, cid, prompt_text=txt, reply_markup=bowl_keyboard())
    asyncio.create_task(_bowl_timeout(client, cid, bowler_id, turn))

async def _bowl_timeout(client, cid, bowler_id, turn):
    await asyncio.sleep(Config.BOWL_TIMEOUT)
    m = solo_matches.get(cid)
    if not m or m.turn_id != turn or m.phase != GamePhase.BOWLING: return
    m.turn_id += 1
    state.pending_bowl.pop(bowler_id, None)
    bowler = m.players[bowler_id]
    bowler.consecutive_penalties += 1
    m.bowler_number = None
    await client.send_message(cid, f"⏱️ {mention(bowler_id, bowler.full_name)} didn't bowl in time — dot ball!")
    await _prompt_batter(client, cid, m.current_batter_id, bowler_id)

async def resolve_solo_bowl(client, bowler_id, number):
    p = state.pending_bowl.get(bowler_id)
    if not p or p.get("kind") != "solo": return
    cid = p["chat_id"]; m = solo_matches.get(cid)
    if not m or m.turn_id != p["turn_id"] or m.phase != GamePhase.BOWLING:
        state.pending_bowl.pop(bowler_id, None); return

    # Spam-free: same number twice in a row blocked
    if cid in state.spam_free_chats:
        bowler = m.players[bowler_id]
        if bowler.last_bowl_number == number:
            await client.send_message(bowler_id,
                f"⛔ **Spam-Free ON!** You bowled {number} last time — send a different number!")
            return

    m.turn_id += 1
    state.pending_bowl.pop(bowler_id, None)
    m.bowler_number = number
    m.players[bowler_id].last_bowl_number = number
    await client.send_message(bowler_id, "✅ Ball bowled! 🎯")
    await _prompt_batter(client, cid, m.current_batter_id, bowler_id)

async def _prompt_batter(client, cid, batter_id, bowler_id):
    m = solo_matches.get(cid)
    if not m: return
    batter         = m.players[batter_id]
    m.phase        = GamePhase.BATTING
    m.turn_id     += 1; turn = m.turn_id
    await client.send_message(cid, bat_prompt(batter_id, batter.full_name, m.bowl_number, m.overs))
    asyncio.create_task(_bat_timeout(client, cid, batter_id, bowler_id, turn))

async def _bat_timeout(client, cid, batter_id, bowler_id, turn):
    await asyncio.sleep(Config.BAT_TIMEOUT)
    m = solo_matches.get(cid)
    if not m or m.turn_id != turn or m.phase != GamePhase.BATTING: return
    m.turn_id += 1
    await _resolve(client, cid, batter_id, bowler_id, None, timed_out=True)

async def resolve_solo_bat(client, cid, batter_id, number):
    m = solo_matches.get(cid)
    if not m or m.phase != GamePhase.BATTING or m.current_batter_id != batter_id: return
    m.turn_id += 1
    await _resolve(client, cid, batter_id, m.current_bowler_id, number, timed_out=False)

async def _resolve(client, cid, batter_id, bowler_id, bat_num, timed_out):
    m = solo_matches.get(cid)
    if not m: return
    batter  = m.players[batter_id]
    bowler  = m.players[bowler_id]
    bowl_n  = m.bowler_number
    bowler.balls_bowled += 1

    if timed_out:
        batter.is_out = True; batter.ball_log.append("W"); bowler.wickets += 1
        await client.send_message(cid, f"⏱️ {mention(batter_id, batter.full_name)} timed out — **OUT!**")
        await send_wicket_gif(client, cid, batter_id, batter.full_name)
    elif bowl_n is not None and bat_num == bowl_n:
        batter.is_out = True; batter.ball_log.append("W"); bowler.wickets += 1
        await send_wicket_gif(client, cid, batter_id, batter.full_name)
    else:
        runs = bat_num if bat_num is not None else 0
        batter.runs += runs; batter.balls += 1; batter.ball_log.append(runs)
        bowler.runs_given += runs
        if runs == 4: batter.fours += 1
        elif runs == 6: batter.sixes += 1
        if runs == 0: batter.zeros_this_over += 1
        await send_run_gif(client, cid, runs, batter_id, batter.full_name)
        if batter.runs in (50, 100):
            await client.send_message(cid, century_msg(batter_id, batter.full_name, batter.runs))

    m.bowler_number = None

    # Batter done when all balls faced OR out
    batter_done = batter.is_out or batter.balls >= m.overs
    if not batter.is_out and batter.balls >= m.overs:
        batter.is_out = True  # used innings, mark done

    if batter_done:
        # Switch bowler only when batter is done (full over completed)
        m.current_bowler_idx += 1
        m.bowl_number = 0          # reset ball counter for next batter's over
        batter.zeros_this_over = 0 # reset dot-ball counter

    remaining = [uid for uid in m.order if not m.players[uid].is_out]
    if not remaining: await _finish(client, cid)
    else: await _next_ball(client, cid)

async def _finish(client, cid):
    m = solo_matches.get(cid)
    if not m: return
    m.phase = GamePhase.FINISHED
    state.pending_bowl.pop(m.current_bowler_id, None)
    if not m.players: solo_matches.pop(cid, None); return

    best_bat = max(m.players.values(), key=lambda p: p.runs)
    best_bwl = max(m.players.values(), key=lambda p: p.wickets)
    motm     = max(m.players.values(), key=lambda p: p.runs + p.wickets * 15)

    await client.send_message(cid, solo_result_card(
        [vars(p) for p in m.players.values()], m.overs,
        best_bat.full_name, best_bwl.full_name, motm.full_name))
    await send_trophy_gif(client, cid, f"⭐ **Player of the Match:** {mention(motm.user_id, motm.full_name)}")

    for p in m.players.values():
        await update_batting_stats(p.user_id, p.full_name, p.runs, p.balls, p.fours, p.sixes, p.is_out, won=(p.user_id==best_bat.user_id))
        if p.balls_bowled > 0:
            await update_bowling_stats(p.user_id, p.full_name, p.wickets, p.runs_given, p.balls_bowled, p.wickets >= 3)
    await update_motm(motm.user_id, motm.full_name)
    solo_matches.pop(cid, None)

# ── Input handlers ────────────────────────────────────────────────────────────

def _bowl_pend(_, __, m): return bool(m.from_user) and state.pending_bowl.get(m.from_user.id, {}).get("kind") == "solo"
def _bat_turn(_, __, m):
    match = solo_matches.get(getattr(m.chat, "id", None))
    return bool(match and match.phase == GamePhase.BATTING and m.from_user and m.from_user.id == match.current_batter_id)

solo_bowl_f = filters.create(_bowl_pend)
solo_bat_f  = filters.create(_bat_turn)

@Client.on_message(filters.private & filters.regex(r"^\s*\d{1,2}\s*$") & solo_bowl_f)
async def on_bowl_dm(client, msg: Message):
    n = int(msg.text.strip())
    if not 1 <= n <= 6: return await msg.reply("⚠️ 1 se 6 ke beech number bhejo!")
    await resolve_solo_bowl(client, msg.from_user.id, n)

@Client.on_message(filters.group & filters.regex(r"^\s*\d{1,2}\s*$") & solo_bat_f)
async def on_bat_gc(client, msg: Message):
    n = int(msg.text.strip())
    m = solo_matches.get(msg.chat.id)
    if not m: return

    # 0 is a valid dot-ball choice — limit to MAX_ZEROS_PER_OVER per over
    if n == 0:
        batter = m.players.get(msg.from_user.id)
        if batter and batter.zeros_this_over >= Config.MAX_ZEROS_PER_OVER:
            return await msg.reply(f"⛔ Max {Config.MAX_ZEROS_PER_OVER} dot balls per over! Send 1–6.")
    elif not 1 <= n <= 6:
        return
    await resolve_solo_bat(client, msg.chat.id, msg.from_user.id, n)
