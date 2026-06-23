import asyncio
import random
from pyrogram import Client, filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from config import Config
from utils.state import solo_matches, SoloMatch, PlayerScore, GamePhase
import utils.state as state
from utils.ui import (
    solo_scorecard, solo_result_card, bat_prompt, bowl_prompt, bowl_keyboard,
    dot_ball_msg, century_msg
)
from utils.gifs import (
    send_run_gif, send_wicket_gif, send_bowling_prompt_gif,
    send_match_start_gif, send_trophy_gif
)
from database.stats import update_batting_stats, update_bowling_stats, update_motm

ADMIN_STATUSES = (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)

async def is_group_admin(client, chat_id: int, user_id: int) -> bool:
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in ADMIN_STATUSES
    except Exception:
        return False

# ── Mode menu (called from plugins/start.py — NOT a handler itself) ───────────

async def show_mode_menu(client: Client, message: Message):
    chat_id = message.chat.id
    if chat_id in solo_matches or chat_id in state.team_matches:
        return await message.reply("⚠️ Ek match already chal raha hai is group mein!")

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🧍 Solo Match", callback_data=f"mode_solo_{message.from_user.id}"),
        InlineKeyboardButton("👥 Team Match", callback_data=f"mode_team_{message.from_user.id}"),
    ]])
    await message.reply(
        "🏏 **Choose Your Battle!**\n\n"
        "🧍 **Solo Match** — Every man for himself.\n"
        "👥 **Team Match** — Two sides, one champion.",
        reply_markup=kb
    )

@Client.on_callback_query(filters.regex("^mode_solo_"))
async def choose_solo_mode(client: Client, cb: CallbackQuery):
    host_id = int(cb.data.split("_")[-1])
    if cb.from_user.id != host_id:
        return await cb.answer("🔒 Sirf match starter choose kar sakta hai!", show_alert=True)

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("3 Balls/Over", callback_data=f"soloovers_3_{host_id}"),
        InlineKeyboardButton("6 Balls/Over", callback_data=f"soloovers_6_{host_id}"),
    ]])
    await cb.message.edit_text("🧍 **Solo Match**\n\nChoose balls per over 👇", reply_markup=kb)
    await cb.answer()

@Client.on_callback_query(filters.regex("^soloovers_"))
async def solo_set_overs(client: Client, cb: CallbackQuery):
    _, overs, host_id = cb.data.split("_")
    overs, host_id = int(overs), int(host_id)
    if cb.from_user.id != host_id:
        return await cb.answer("🔒 Sirf match starter choose kar sakta hai!", show_alert=True)

    chat_id = cb.message.chat.id
    match = SoloMatch(chat_id=chat_id, host_id=host_id, overs=overs, phase=GamePhase.JOINING)
    solo_matches[chat_id] = match

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🙋 Join Match", callback_data=f"joinsolo_{chat_id}")]])
    msg = await cb.message.edit_text(
        f"🧍 **SOLO MATCH STARTING!**\n\n"
        f"🎯 {overs} Ball{'s' if overs > 1 else ''}/Over\n"
        f"👥 Min {Config.MIN_PLAYERS_SOLO} — Max {Config.MAX_PLAYERS_SOLO} players\n\n"
        f"⏱️ Joining closes in **2 minutes**\n"
        f"Tap below or type `/join_solo` to join!",
        reply_markup=kb
    )
    match.join_msg_id = msg.id
    await cb.answer()
    asyncio.create_task(auto_start_timer(client, chat_id))

async def auto_start_timer(client: Client, chat_id: int):
    await asyncio.sleep(Config.JOIN_TIMEOUT)
    match = solo_matches.get(chat_id)
    if match and match.phase == GamePhase.JOINING:
        if len(match.players) >= Config.MIN_PLAYERS_SOLO:
            await begin_solo_match(client, chat_id)
        else:
            await client.send_message(
                chat_id,
                f"⚠️ **Match Cancelled!** Not enough players (need min {Config.MIN_PLAYERS_SOLO})."
            )
            solo_matches.pop(chat_id, None)

@Client.on_callback_query(filters.regex("^joinsolo_"))
async def join_solo_callback(client: Client, cb: CallbackQuery):
    await _join_solo(client, int(cb.data.split("_")[1]), cb.from_user, cb)

@Client.on_message(filters.command("join_solo") & filters.group)
async def join_solo_cmd(client: Client, message: Message):
    await _join_solo(client, message.chat.id, message.from_user, message)

async def _join_solo(client, chat_id, user, ctx):
    match  = solo_matches.get(chat_id)
    is_cb  = isinstance(ctx, CallbackQuery)
    def reply(msg): return ctx.answer(msg, show_alert=True) if is_cb else ctx.reply(msg)

    if not match or match.phase != GamePhase.JOINING:
        return await reply("⚠️ No joining window open right now!")
    if user.id in match.players:
        return await reply("✅ Tu already joined hai!")
    if len(match.players) >= Config.MAX_PLAYERS_SOLO:
        return await reply("⚠️ Match full hai!")

    match.players[user.id] = PlayerScore(user_id=user.id, full_name=user.full_name)
    match.order.append(user.id)

    names = "\n".join(f"  {i+1}. {p.full_name}" for i, p in enumerate(match.players.values()))
    try:
        await client.edit_message_text(
            chat_id, match.join_msg_id,
            f"🧍 **SOLO MATCH — JOINING**\n\n"
            f"👥 **Players ({len(match.players)}):**\n{names}\n\n"
            f"Type `/join_solo` to join!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🙋 Join Match", callback_data=f"joinsolo_{chat_id}")
            ]])
        )
    except Exception:
        pass

    if is_cb:
        await ctx.answer("✅ Joined!")
    else:
        await ctx.reply(f"✅ **{user.full_name}** joined the match!")

@Client.on_message(filters.command("leave_solo") & filters.group)
async def leave_solo_cmd(client: Client, message: Message):
    match = solo_matches.get(message.chat.id)
    if not match or match.phase != GamePhase.JOINING:
        return await message.reply("⚠️ No joining window open!")
    uid = message.from_user.id
    if uid not in match.players:
        return await message.reply("⚠️ Tu joined nahi hai!")
    del match.players[uid]
    match.order.remove(uid)
    await message.reply(f"👋 **{message.from_user.full_name}** left the match.")

@Client.on_message(filters.command("solo_list") & filters.group)
async def solo_list_cmd(client: Client, message: Message):
    match = solo_matches.get(message.chat.id)
    if not match:
        return await message.reply("⚠️ No active solo match!")
    names = "\n".join(f"  {i+1}. {p.full_name}" for i, p in enumerate(match.players.values()))
    await message.reply(f"👥 **Joined Players ({len(match.players)}):**\n{names or 'None yet'}")

@Client.on_message(filters.command("start_solo") & filters.group)
async def force_start_solo(client: Client, message: Message):
    if not await is_group_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("🔒 Only group admins can force-start!")
    match = solo_matches.get(message.chat.id)
    if not match or match.phase != GamePhase.JOINING:
        return await message.reply("⚠️ No joining window open!")
    if len(match.players) < Config.MIN_PLAYERS_SOLO:
        return await message.reply(f"⚠️ Need min {Config.MIN_PLAYERS_SOLO} players!")
    await begin_solo_match(client, message.chat.id)

@Client.on_message(filters.command("extend_solo") & filters.group)
async def extend_solo_cmd(client: Client, message: Message):
    if not await is_group_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("🔒 Only group admins can extend!")
    match = solo_matches.get(message.chat.id)
    if not match or match.phase != GamePhase.JOINING:
        return await message.reply("⚠️ No joining window open!")
    await message.reply("⏱️ **Joining time extended by 30 seconds!**")
    asyncio.create_task(_extend_timer(client, message.chat.id))

async def _extend_timer(client, chat_id):
    await asyncio.sleep(30)
    match = solo_matches.get(chat_id)
    if match and match.phase == GamePhase.JOINING:
        if len(match.players) >= Config.MIN_PLAYERS_SOLO:
            await begin_solo_match(client, chat_id)
        else:
            await client.send_message(chat_id, "⚠️ **Match Cancelled!** Not enough players.")
            solo_matches.pop(chat_id, None)

@Client.on_message(filters.command("resume_solo") & filters.group)
async def resume_solo_cmd(client: Client, message: Message):
    if not await is_group_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("🔒 Only group admins can resume!")
    match = solo_matches.get(message.chat.id)
    if not match:
        return await message.reply("⚠️ No interrupted match found!")
    await message.reply("▶️ **Resuming match...**")
    await next_ball(client, message.chat.id)

@Client.on_message(filters.command("end_solo") & filters.group)
async def end_solo_cmd(client: Client, message: Message):
    if not await is_group_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("🔒 Only group admins can end the match!")
    match = solo_matches.pop(message.chat.id, None)
    if match:
        state.pending_bowl.pop(match.current_bowler_id, None)
        await message.reply("🛑 **Solo match ended!**")
    else:
        await message.reply("⚠️ No active solo match!")

@Client.on_message(filters.command("solo_score") & filters.group)
async def solo_score_cmd(client: Client, message: Message):
    match = solo_matches.get(message.chat.id)
    if not match:
        return await message.reply("⚠️ No active solo match!")
    await message.reply(solo_scorecard([vars(p) for p in match.players.values()], match.overs))

# ── Core Match Flow ───────────────────────────────────────────────────────────

async def begin_solo_match(client: Client, chat_id: int):
    match = solo_matches[chat_id]
    match.phase = GamePhase.BOWLING
    random.shuffle(match.order)

    await send_match_start_gif(client, chat_id)
    await client.send_message(
        chat_id,
        f"🏏 **MATCH STARTED!**\n\n"
        f"👥 {len(match.players)} players ready!\n"
        f"🎯 {match.overs} ball{'s' if match.overs > 1 else ''} per over\n\n"
        f"Let the game begin! 🔥"
    )
    await next_ball(client, chat_id)

async def next_ball(client: Client, chat_id: int):
    match = solo_matches.get(chat_id)
    if not match:
        return

    remaining = [uid for uid in match.order if not match.players[uid].is_out]
    if not remaining:
        return await finish_solo_match(client, chat_id)

    batter_id = remaining[0]
    bowler_candidates = [uid for uid in match.order if uid != batter_id]
    bowler_id = bowler_candidates[match.current_bowler_idx % len(bowler_candidates)] if bowler_candidates else batter_id

    match.bowl_number      += 1
    match.phase             = GamePhase.BOWLING
    match.current_batter_id = batter_id
    match.current_bowler_id = bowler_id
    match.turn_id           += 1
    turn = match.turn_id

    state.pending_bowl[bowler_id] = {"chat_id": chat_id, "kind": "solo", "turn_id": turn}

    bowler = match.players[bowler_id]
    await send_bowling_prompt_gif(client, chat_id)
    await client.send_message(
        chat_id,
        bowl_prompt(bowler.full_name, match.bowl_number, match.overs),
        reply_markup=bowl_keyboard()     # ← DM button
    )
    asyncio.create_task(_bowl_timeout(client, chat_id, bowler_id, turn))

async def _bowl_timeout(client, chat_id, bowler_id, turn):
    await asyncio.sleep(Config.BOWL_TIMEOUT)
    match = solo_matches.get(chat_id)
    if not match or match.turn_id != turn or match.phase != GamePhase.BOWLING:
        return
    match.turn_id += 1
    state.pending_bowl.pop(bowler_id, None)
    bowler = match.players[bowler_id]
    bowler.consecutive_penalties += 1
    bowler.runs_given -= 6
    match.bowler_number = None
    await client.send_message(
        chat_id,
        f"⏱️ **Time's up!** {bowler.full_name} didn't bowl — dot ball + penalty!"
    )
    await _prompt_batter(client, chat_id, match.current_batter_id, bowler_id)

async def resolve_solo_bowl(client, bowler_id: int, number: int):
    pending = state.pending_bowl.get(bowler_id)
    if not pending or pending.get("kind") != "solo":
        return
    chat_id = pending["chat_id"]
    match   = solo_matches.get(chat_id)
    if not match or match.turn_id != pending["turn_id"] or match.phase != GamePhase.BOWLING:
        state.pending_bowl.pop(bowler_id, None)
        return

    # ── Spam-free check ──────────────────────────────────────────────────────
    if chat_id in state.spam_free_chats:
        bowler = match.players[bowler_id]
        if bowler.last_bowl_number == number:
            await client.send_message(
                bowler_id,
                f"⛔ **Spam-Free ON!** You already bowled {number} last time.\n"
                f"Send a different number (1–6)!"
            )
            return  # keep pending, bowler must try again

    match.turn_id += 1
    state.pending_bowl.pop(bowler_id, None)
    match.bowler_number = number
    match.players[bowler_id].last_bowl_number = number
    await client.send_message(bowler_id, "✅ Got it! Ball is bowled... 🎯")
    await _prompt_batter(client, chat_id, match.current_batter_id, bowler_id)

async def _prompt_batter(client, chat_id, batter_id, bowler_id):
    match = solo_matches.get(chat_id)
    if not match:
        return
    batter = match.players[batter_id]
    match.phase             = GamePhase.BATTING
    match.current_batter_id = batter_id
    match.turn_id           += 1
    turn = match.turn_id
    await client.send_message(chat_id, bat_prompt(batter.full_name, match.bowl_number))
    asyncio.create_task(_bat_timeout(client, chat_id, batter_id, bowler_id, turn))

async def _bat_timeout(client, chat_id, batter_id, bowler_id, turn):
    await asyncio.sleep(Config.BAT_TIMEOUT)
    match = solo_matches.get(chat_id)
    if not match or match.turn_id != turn or match.phase != GamePhase.BATTING:
        return
    match.turn_id += 1
    await _resolve_ball(client, chat_id, batter_id, bowler_id, None, timed_out=True)

async def resolve_solo_bat(client, chat_id, batter_id, number):
    match = solo_matches.get(chat_id)
    if not match or match.phase != GamePhase.BATTING or match.current_batter_id != batter_id:
        return
    match.turn_id += 1
    await _resolve_ball(client, chat_id, batter_id, match.current_bowler_id, number, timed_out=False)

async def _resolve_ball(client, chat_id, batter_id, bowler_id, bat_number, timed_out):
    match = solo_matches.get(chat_id)
    if not match:
        return

    batter = match.players[batter_id]
    bowler = match.players[bowler_id]
    bowl_n = match.bowler_number

    bowler.balls_bowled += 1

    if timed_out:
        batter.is_out = True
        batter.ball_log.append("W")
        bowler.wickets += 1
        await client.send_message(chat_id, "⏱️ **Time's up!** Auto OUT!")
        await send_wicket_gif(client, chat_id, batter.full_name)
    elif bowl_n is not None and bat_number == bowl_n:
        batter.is_out = True
        batter.ball_log.append("W")
        bowler.wickets += 1
        await send_wicket_gif(client, chat_id, batter.full_name)
    else:
        runs = bat_number
        batter.runs  += runs
        batter.balls += 1
        batter.ball_log.append(runs)
        bowler.runs_given += runs
        if runs == 4:
            batter.fours += 1
        elif runs == 6:
            batter.sixes += 1
        if runs == 0:
            batter.zeros_this_over += 1
            await client.send_message(chat_id, dot_ball_msg(batter.full_name))
        else:
            await send_run_gif(client, chat_id, runs, batter.full_name)
        if batter.runs in (50, 100):
            await client.send_message(chat_id, century_msg(batter.full_name, batter.runs))

    match.bowler_number = None

    if not batter.is_out and batter.balls >= match.overs:
        batter.is_out = True
    match.current_bowler_idx += 1

    # Reset per-over zero counter every `overs` balls
    if batter.balls > 0 and batter.balls % match.overs == 0:
        batter.zeros_this_over = 0

    remaining = [uid for uid in match.order if not match.players[uid].is_out]
    if not remaining:
        await finish_solo_match(client, chat_id)
    else:
        await next_ball(client, chat_id)

async def finish_solo_match(client: Client, chat_id: int):
    match = solo_matches.get(chat_id)
    if not match:
        return
    match.phase = GamePhase.FINISHED
    state.pending_bowl.pop(match.current_bowler_id, None)

    if not match.players:
        solo_matches.pop(chat_id, None)
        return

    best_batter = max(match.players.values(), key=lambda p: p.runs)
    best_bowler = max(match.players.values(), key=lambda p: p.wickets)
    motm        = max(match.players.values(), key=lambda p: p.runs + p.wickets * 15)

    await client.send_message(
        chat_id,
        solo_result_card(
            [vars(p) for p in match.players.values()], match.overs,
            best_batter.full_name, best_bowler.full_name, motm.full_name
        )
    )
    await send_trophy_gif(client, chat_id, f"⭐ **Player of the Match:** {motm.full_name}")

    for p in match.players.values():
        await update_batting_stats(
            p.user_id, p.full_name, p.runs, p.balls, p.fours, p.sixes,
            p.is_out, won=(p.user_id == best_batter.user_id)
        )
        if p.balls_bowled > 0:
            await update_bowling_stats(
                p.user_id, p.full_name, p.wickets, p.runs_given, p.balls_bowled, p.wickets >= 3
            )
    await update_motm(motm.user_id, motm.full_name)
    solo_matches.pop(chat_id, None)

# ── Input Filters & Handlers (no pyromod) ────────────────────────────────────

def _solo_bowl_pending(_, __, m: Message) -> bool:
    return bool(m.from_user) and state.pending_bowl.get(m.from_user.id, {}).get("kind") == "solo"

def _solo_bat_turn(_, __, m: Message) -> bool:
    match = solo_matches.get(getattr(m.chat, "id", None))
    return bool(
        match and match.phase == GamePhase.BATTING
        and m.from_user and m.from_user.id == match.current_batter_id
    )

solo_bowl_filter = filters.create(_solo_bowl_pending)
solo_bat_filter  = filters.create(_solo_bat_turn)

@Client.on_message(filters.private & filters.regex(r"^\s*\d{1,3}\s*$") & solo_bowl_filter)
async def solo_bowl_dm_input(client: Client, message: Message):
    number = int(message.text.strip())
    if not (1 <= number <= 6):
        return await message.reply("⚠️ Send a number between 1–6!")
    await resolve_solo_bowl(client, message.from_user.id, number)

@Client.on_message(filters.group & filters.regex(r"^\s*\d{1,3}\s*$") & solo_bat_filter)
async def solo_bat_group_input(client: Client, message: Message):
    number = int(message.text.strip())
    if not (1 <= number <= 6):
        return

    match = solo_matches.get(message.chat.id)
    if not match:
        return

    # ── Dot-ball spam limit: max 2 zeros per over ────────────────────────────
    if number == 0:
        batter = match.players.get(message.from_user.id)
        if batter and batter.zeros_this_over >= Config.MAX_ZEROS_PER_OVER:
            return await message.reply(
                f"⛔ Max {Config.MAX_ZEROS_PER_OVER} dot balls per over!\n"
                f"Send a number between **1–6**."
            )

    await resolve_solo_bat(client, message.chat.id, message.from_user.id, number)
