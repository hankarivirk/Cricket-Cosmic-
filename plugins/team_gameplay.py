import asyncio
from pyrogram import Client, filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import Message
from config import Config
from utils.state import team_matches, GamePhase
import utils.state as state
from utils.ui import team_scorecard, team_result_card, bat_prompt, bowl_prompt, bowl_keyboard, dot_ball_msg, century_msg, innings_break_msg, mention
from utils.gifs import send_run_gif, send_wicket_gif, send_bowling_prompt_gif, send_trophy_gif
from database.stats import update_batting_stats, update_bowling_stats, update_motm

ADMIN_S = (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)

def _team(m, s): return m.team_a if s == "A" else m.team_b
def _cap(m, s):  return m.cap_a  if s == "A" else m.cap_b

async def _is_admin(client, cid, uid):
    try: return (await client.get_chat_member(cid, uid)).status in ADMIN_S
    except: return False

@Client.on_message(filters.command("bowling") & filters.group)
async def cmd_bowling(client, msg: Message):
    m = team_matches.get(msg.chat.id)
    if not m: return await msg.reply("⚠️ No active match!")
    if msg.from_user.id != _cap(m, m.bowling_team): return await msg.reply("🔒 Bowling captain only!")
    if not msg.reply_to_message: return await msg.reply("⚠️ Reply to the player you want to bowl!")
    bid = msg.reply_to_message.from_user.id
    bt  = _team(m, m.bowling_team)
    if bid not in bt: return await msg.reply("⚠️ Player not in bowling team!")
    m.current_bowler = bid
    await msg.reply(f"🎯 {mention(bid, bt[bid].full_name)} will bowl this over!")
    if m.striker is None:
        batt  = _team(m, m.batting_team)
        bcap  = _cap(m, m.batting_team)
        await msg.reply(f"👉 {mention(bcap, batt[bcap].full_name)} (batting captain) — choose opener:\n`/batting` (reply to player)")
    else:
        await _start_over(client, msg.chat.id)

@Client.on_message(filters.command("batting") & filters.group)
async def cmd_batting(client, msg: Message):
    m = team_matches.get(msg.chat.id)
    if not m: return await msg.reply("⚠️ No active match!")
    if msg.from_user.id != _cap(m, m.batting_team): return await msg.reply("🔒 Batting captain only!")
    if not msg.reply_to_message: return await msg.reply("⚠️ Reply to the player you want to bat!")
    pid = msg.reply_to_message.from_user.id
    bt  = _team(m, m.batting_team)
    if pid not in bt: return await msg.reply("⚠️ Player not in batting team!")
    if bt[pid].is_out: return await msg.reply("⚠️ Player already out!")

    if m.striker is None: m.striker = pid
    elif m.non_striker is None and pid != m.striker: m.non_striker = pid
    else: m.striker = pid

    await msg.reply(f"🏏 {mention(pid, bt[pid].full_name)} is on strike!")

    if m.current_bowler:
        if m.ball_count > 0:
            # Mid-over wicket: continue same over, don't reset ball_count
            await _continue_over(client, msg.chat.id)
        else:
            await _start_over(client, msg.chat.id)

@Client.on_message(filters.command("score") & filters.group)
async def cmd_score(client, msg: Message):
    m = team_matches.get(msg.chat.id)
    if not m: return await msg.reply("⚠️ No active match!")
    await msg.reply(team_scorecard(m))

@Client.on_message(filters.command("change_cap") & filters.group)
async def cmd_change_cap(client, msg: Message):
    m = team_matches.get(msg.chat.id)
    if not m or msg.from_user.id != m.host_id: return await msg.reply("🔒 Host only!")
    if not msg.reply_to_message: return await msg.reply("⚠️ Reply to new captain!")
    nc = msg.reply_to_message.from_user.id
    if nc in m.team_a: m.cap_a = nc; await msg.reply(f"👑 {mention(nc, m.team_a[nc].full_name)} is now Team A Captain!")
    elif nc in m.team_b: m.cap_b = nc; await msg.reply(f"👑 {mention(nc, m.team_b[nc].full_name)} is now Team B Captain!")
    else: await msg.reply("⚠️ Player not found in any team!")

@Client.on_message(filters.command("end_match") & filters.group)
async def cmd_end_match(client, msg: Message):
    m = team_matches.get(msg.chat.id)
    if not m: return
    if msg.from_user.id != m.host_id and not await _is_admin(client, msg.chat.id, msg.from_user.id):
        return await msg.reply("🔒 Host or admin only!")
    state.pending_bowl.pop(m.current_bowler, None)
    del team_matches[msg.chat.id]
    await msg.reply("🛑 Match ended!")

# ── Over Flow ─────────────────────────────────────────────────────────────────

async def _start_over(client, cid):
    """Call at the START of a new over — resets ball_count to 0."""
    m = team_matches.get(cid)
    if not m or not m.current_bowler: return
    m.ball_count = 0
    await _send_bowl_prompt(client, cid)

async def _continue_over(client, cid):
    """Call after a mid-over wicket — keeps ball_count as-is."""
    await _send_bowl_prompt(client, cid)

async def _send_bowl_prompt(client, cid):
    m = team_matches.get(cid)
    if not m or not m.current_bowler: return
    bt      = _team(m, m.bowling_team)
    bowler  = bt[m.current_bowler]
    m.turn_id += 1; turn = m.turn_id
    state.pending_bowl[m.current_bowler] = {"chat_id": cid, "kind": "team", "turn_id": turn}

    txt = bowl_prompt(
        m.current_bowler, bowler.full_name,
        m.ball_count + 1, 6,
        m.over_count + 1, m.overs)
    await send_bowling_prompt_gif(client, cid, prompt_text=txt, reply_markup=bowl_keyboard())
    asyncio.create_task(_bowl_to(client, cid, m.current_bowler, turn))

async def _bowl_to(client, cid, bid, turn):
    await asyncio.sleep(Config.BOWL_TIMEOUT)
    m = team_matches.get(cid)
    if not m or m.turn_id != turn: return
    m.turn_id += 1; state.pending_bowl.pop(bid, None)
    bt = _team(m, m.bowling_team)
    await client.send_message(cid, f"⏱️ {mention(bid, bt[bid].full_name)} didn't bowl — dot ball!")
    m.bowler_number = None
    await _prompt_batter(client, cid)

async def resolve_team_bowl(client, bid, number):
    p = state.pending_bowl.get(bid)
    if not p or p.get("kind") != "team": return
    cid = p["chat_id"]; m = team_matches.get(cid)
    if not m or m.turn_id != p["turn_id"]: state.pending_bowl.pop(bid, None); return

    if cid in state.spam_free_chats:
        bt = _team(m, m.bowling_team)
        bw = bt.get(bid)
        if bw and bw.last_bowl_number == number:
            await client.send_message(bid, f"⛔ **Spam-Free!** You bowled {number} last time — send different!"); return

    m.turn_id += 1; state.pending_bowl.pop(bid, None)
    m.bowler_number = number
    bt = _team(m, m.bowling_team)
    if bid in bt: bt[bid].last_bowl_number = number
    await client.send_message(bid, "✅ Ball bowled! 🎯")
    await _prompt_batter(client, cid)

async def _prompt_batter(client, cid):
    m = team_matches.get(cid)
    if not m or m.striker is None: return
    bt = _team(m, m.batting_team); striker = bt[m.striker]
    m.turn_id += 1; turn = m.turn_id
    await client.send_message(cid, bat_prompt(m.striker, striker.full_name, m.ball_count + 1, 6))
    asyncio.create_task(_bat_to(client, cid, turn))

async def _bat_to(client, cid, turn):
    await asyncio.sleep(Config.BAT_TIMEOUT)
    m = team_matches.get(cid)
    if not m or m.turn_id != turn: return
    m.turn_id += 1
    await _resolve_ball(client, cid, None, timed_out=True)

async def resolve_team_bat(client, cid, sid, number):
    m = team_matches.get(cid)
    if not m or m.striker != sid: return
    m.turn_id += 1
    await _resolve_ball(client, cid, number, timed_out=False)

async def _resolve_ball(client, cid, bat_num, timed_out):
    m = team_matches.get(cid)
    if not m: return
    btt     = _team(m, m.batting_team); blt = _team(m, m.bowling_team)
    striker = btt[m.striker]; bowler = blt[m.current_bowler]
    bowl_n  = m.bowler_number

    m.ball_count += 1; bowler.balls_bowled += 1
    is_wkt = False

    if timed_out:
        is_wkt = True
        await client.send_message(cid, f"⏱️ {mention(m.striker, striker.full_name)} timed out — **OUT!**")
        await send_wicket_gif(client, cid, m.striker, striker.full_name)
    elif bowl_n is not None and bat_num == bowl_n:
        is_wkt = True
        await send_wicket_gif(client, cid, m.striker, striker.full_name)
    else:
        runs = bat_num if bat_num is not None else 0
        striker.runs += runs; striker.balls += 1
        if runs == 4: striker.fours += 1
        elif runs == 6: striker.sixes += 1
        bowler.runs_given += runs
        if m.batting_team == "A": m.team_a_score += runs
        else: m.team_b_score += runs
        if runs == 0: striker.zeros_this_over += 1
        await send_run_gif(client, cid, runs, m.striker, striker.full_name)
        if striker.runs in (50, 100):
            await client.send_message(cid, century_msg(m.striker, striker.full_name, striker.runs))
        if runs % 2 == 1 and m.non_striker:
            m.striker, m.non_striker = m.non_striker, m.striker

    if is_wkt:
        striker.is_out = True; bowler.wickets += 1
        if m.batting_team == "A": m.team_a_wickets += 1
        else: m.team_b_wickets += 1
        m.last_3_wickets.append(m.current_bowler)
        if len(m.last_3_wickets) >= 3 and len(set(m.last_3_wickets[-3:])) == 1:
            await client.send_message(cid, f"🎩 **HAT-TRICK!** {mention(m.current_bowler, bowler.full_name)} 🔥")
        m.striker = m.non_striker; m.non_striker = None

    m.bowler_number = None

    # Target chase win check
    if m.innings == 2 and m.target:
        curr = m.team_a_score if m.batting_team == "A" else m.team_b_score
        if curr >= m.target: return await _finish_match(client, cid)

    wkts = m.team_a_wickets if m.batting_team == "A" else m.team_b_wickets
    size = len(_team(m, m.batting_team))
    all_out   = wkts >= max(size - 1, 1)
    # ── FIXED: 1 over = 6 balls ──────────────────────────────────────────────
    over_done = m.ball_count >= 6

    if all_out:
        return await _end_innings(client, cid)

    if over_done:
        m.over_count += 1
        m.ball_count  = 0
        # Reset dot-ball counters for next over
        for p in _team(m, m.batting_team).values():
            p.zeros_this_over = 0
        if m.over_count >= m.overs:
            return await _end_innings(client, cid)
        # More overs — new bowler needed
        m.current_bowler = None
        bwl_cap = _cap(m, m.bowling_team); bwlt = _team(m, m.bowling_team)
        await client.send_message(cid,
            f"📋 **Over {m.over_count} complete!**\n\n"
            f"👉 {mention(bwl_cap, bwlt[bwl_cap].full_name)} (bowling captain) — choose next bowler:\n`/bowling` (reply to player)")
        return

    if m.striker is None:
        bat_cap = _cap(m, m.batting_team); batt = _team(m, m.batting_team)
        await client.send_message(cid,
            f"👉 {mention(bat_cap, batt[bat_cap].full_name)} (batting captain) — choose next batter:\n`/batting` (reply to player)")
    else:
        await _prompt_batter(client, cid)

async def _end_innings(client, cid):
    m = team_matches.get(cid)
    if not m: return
    if m.innings == 1:
        score = m.team_a_score if m.batting_team == "A" else m.team_b_score
        wkts  = m.team_a_wickets if m.batting_team == "A" else m.team_b_wickets
        m.target = score + 1; m.innings = 2
        old_bat  = m.batting_team
        m.batting_team, m.bowling_team = m.bowling_team, m.batting_team
        m.striker = m.non_striker = m.current_bowler = None
        m.ball_count = m.over_count = 0
        old_batt = _team(m, old_bat); old_cap = _cap(m, old_bat)
        await client.send_message(cid, innings_break_msg(old_batt[old_cap].full_name, score, wkts, m.target))
        bwl_cap = _cap(m, m.bowling_team); bwlt = _team(m, m.bowling_team)
        bat_cap = _cap(m, m.batting_team); batt  = _team(m, m.batting_team)
        await client.send_message(cid,
            f"👉 {mention(bwl_cap, bwlt[bwl_cap].full_name)} (bowling captain) — choose bowler:\n`/bowling` (reply to player)\n\n"
            f"👉 {mention(bat_cap, batt[bat_cap].full_name)} (batting captain) — choose opener:\n`/batting` (reply to player)")
    else:
        await _finish_match(client, cid)

async def _finish_match(client, cid):
    m = team_matches.get(cid)
    if not m: return
    m.phase = GamePhase.FINISHED; state.pending_bowl.pop(m.current_bowler, None)
    winner = "🔴 Team A" if m.team_a_score > m.team_b_score else ("🔵 Team B" if m.team_b_score > m.team_a_score else "🤝 Tied")
    all_p  = {**m.team_a, **m.team_b}
    motm   = max(all_p.values(), key=lambda p: p.runs + p.wickets * 15) if all_p else None
    await client.send_message(cid, team_result_card(m, winner, motm.full_name if motm else "N/A"))
    if motm: await send_trophy_gif(client, cid, f"⭐ **Player of the Match:** {mention(motm.user_id, motm.full_name)}")
    won = "A" if "Team A" in winner else ("B" if "Team B" in winner else None)
    for side, td in [("A", m.team_a), ("B", m.team_b)]:
        for p in td.values():
            await update_batting_stats(p.user_id, p.full_name, p.runs, p.balls, p.fours, p.sixes, p.is_out, won=(side==won))
            if p.balls_bowled > 0:
                await update_bowling_stats(p.user_id, p.full_name, p.wickets, p.runs_given, p.balls_bowled, p.wickets >= 3)
    if motm: await update_motm(motm.user_id, motm.full_name)
    del team_matches[cid]

# ── Input handlers ────────────────────────────────────────────────────────────

def _tbp(_, __, m): return bool(m.from_user) and state.pending_bowl.get(m.from_user.id, {}).get("kind") == "team"
def _tbt(_, __, m):
    match = team_matches.get(getattr(m.chat, "id", None))
    return bool(match and match.striker and m.from_user and m.from_user.id == match.striker)

@Client.on_message(filters.private & filters.regex(r"^\s*\d{1,2}\s*$") & filters.create(_tbp))
async def on_team_bowl(client, msg: Message):
    n = int(msg.text.strip())
    if not 1 <= n <= 6: return await msg.reply("⚠️ 1 se 6 ke beech number bhejo!")
    await resolve_team_bowl(client, msg.from_user.id, n)

@Client.on_message(filters.group & filters.regex(r"^\s*\d{1,2}\s*$") & filters.create(_tbt))
async def on_team_bat(client, msg: Message):
    m = team_matches.get(msg.chat.id)
    if not m or not m.current_bowler: return
    n = int(msg.text.strip())
    if n == 0:
        btt = _team(m, m.batting_team); striker = btt.get(msg.from_user.id)
        if striker and striker.zeros_this_over >= Config.MAX_ZEROS_PER_OVER:
            return await msg.reply(f"⛔ Max {Config.MAX_ZEROS_PER_OVER} dot balls per over! Send 1–6.")
    elif not 1 <= n <= 6:
        return
    await resolve_team_bat(client, msg.chat.id, msg.from_user.id, n)
