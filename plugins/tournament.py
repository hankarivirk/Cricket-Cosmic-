import itertools, string
from pyrogram import Client, filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import Message
from config import Config
from utils.state import tournaments, Tournament, TournamentTeam, GamePhase
from utils.gifs import send_trophy_gif

ADMIN_S   = (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
LABELS    = list(string.ascii_uppercase)
MAX_TEAMS = 8

async def _is_admin(client, cid, uid):
    try: return (await client.get_chat_member(cid, uid)).status in ADMIN_S
    except: return False

@Client.on_message(filters.command("tournament") & filters.group)
async def cmd_tournament(client, msg: Message):
    cid = msg.chat.id
    if cid in tournaments: return await msg.reply("⚠️ Tournament already running!")
    args = msg.command[1:]; num, size = 3, 3
    try:
        if len(args) >= 1: num  = int(args[0])
        if len(args) >= 2: size = int(args[1])
    except ValueError:
        return await msg.reply("⚠️ Usage: `/tournament` or `/tournament <teams> <size>`\nExample: `/tournament 4 5`")
    if not 2 <= num <= MAX_TEAMS: return await msg.reply(f"⚠️ Teams: 2–{MAX_TEAMS}!")
    if not 1 <= size <= 20:       return await msg.reply("⚠️ Size: 1–20!")
    labels = LABELS[:num]
    t = Tournament(chat_id=cid, host_id=msg.from_user.id, team_size=size, phase=GamePhase.JOINING)
    for lb in labels: t.teams[lb] = TournamentTeam(name=f"Team {lb}")
    tournaments[cid] = t
    cmds = "  ".join(f"`/t_join_{k}`" for k in labels)
    await msg.reply(
        f"🏆 **TOURNAMENT STARTED!**\n\n"
        f"👑 Host: {msg.from_user.full_name}\n"
        f"🏟️ {num} teams  |  👥 {size} players/team\n\n"
        f"Join your team:\n{cmds}\n\n"
        f"Host starts with `/t_start` once teams are filled.")

async def _join(client, msg: Message, key: str):
    t = tournaments.get(msg.chat.id)
    if not t or t.phase != GamePhase.JOINING: return await msg.reply("⚠️ No tournament joining open!")
    if key not in t.teams: return await msg.reply(f"⚠️ Team {key} doesn't exist!")
    uid  = msg.from_user.id; name = msg.from_user.full_name
    for k, tm in t.teams.items():
        if uid in tm.players: return await msg.reply(f"✅ Already in **Team {k}**!")
    team = t.teams[key]
    if len(team.players) >= t.team_size: return await msg.reply(f"⚠️ Team {key} full! ({t.team_size} max)")
    team.players[uid] = name
    await msg.reply(f"✅ **{name}** joined **Team {key}**! ({len(team.players)}/{t.team_size})")

# ── Register /t_join_A … /t_join_H in module namespace so Pyrogram finds them ─
def _make(label):
    async def _h(client, msg: Message): await _join(client, msg, label)
    _h.__name__ = f"t_join_{label}"
    return Client.on_message(filters.command(f"t_join_{label}") & filters.group)(_h)

for _lb in LABELS[:MAX_TEAMS]:
    globals()[f"t_join_{_lb}"] = _make(_lb)

@Client.on_message(filters.command("t_members") & filters.group)
async def cmd_t_members(client, msg: Message):
    t = tournaments.get(msg.chat.id)
    if not t: return await msg.reply("⚠️ No tournament!")
    lines = [f"👥 **Teams** ({t.team_size}/team)", "━━━━━━━━━━━━━━━━━━━━"]
    for k, tm in t.teams.items():
        names = "\n".join(f"  • {n}" for n in tm.players.values()) or "  — empty"
        lines.append(f"**{tm.name}** ({len(tm.players)}/{t.team_size})\n{names}")
    await msg.reply("\n".join(lines))

@Client.on_message(filters.command("t_score") & filters.group)
async def cmd_t_score(client, msg: Message):
    t = tournaments.get(msg.chat.id)
    if not t: return await msg.reply("⚠️ No tournament!")
    lines = ["🏆 **STANDINGS**", "━━━━━━━━━━━━━━━━━━━━"]
    for i, tm in enumerate(sorted(t.teams.values(), key=lambda x: x.points, reverse=True), 1):
        lines.append(f"{i}. **{tm.name}** — {tm.points} pts ({tm.wins} wins)")
    await msg.reply("\n".join(lines))

@Client.on_message(filters.command("t_start") & filters.group)
async def cmd_t_start(client, msg: Message):
    t = tournaments.get(msg.chat.id)
    if not t or msg.from_user.id != t.host_id: return await msg.reply("🔒 Host only!")
    empty = [k for k, tm in t.teams.items() if len(tm.players) == 0]
    if empty: return await msg.reply(f"⚠️ Empty teams: {', '.join(empty)}")
    t.fixtures = list(itertools.combinations(list(t.teams.keys()), 2))
    t.phase    = GamePhase.WAITING
    lines = [f"🏆 **FIXTURES (Round Robin)**"] + [
        f"  • {t.teams[a].name} vs {t.teams[b].name}" for a, b in t.fixtures]
    lines += ["\nLog results: `/t_result A B A` (Team A beat Team B)\n📊 Standings: `/t_score`"]
    await msg.reply("\n".join(lines))

@Client.on_message(filters.command("t_result") & filters.group)
async def cmd_t_result(client, msg: Message):
    t = tournaments.get(msg.chat.id)
    if not t or msg.from_user.id != t.host_id: return await msg.reply("🔒 Host only!")
    if len(msg.command) < 4: return await msg.reply("⚠️ Usage: `/t_result <A> <B> <winner>`")
    t1, t2, w = (x.upper() for x in msg.command[1:4])
    if w not in t.teams: return await msg.reply("⚠️ Invalid winner!")
    t.teams[w].wins += 1; t.teams[w].points += 2
    t.results.append((t1, t2, w))
    await msg.reply(f"✅ **{t.teams[w].name}** wins vs {t.teams.get(t1, type('',(),{'name':t1})()).name}!")
    if len(t.fixtures) > 0 and len(t.results) >= len(t.fixtures):
        await _announce(client, msg.chat.id)

async def _announce(client, cid):
    t = tournaments.get(cid)
    if not t: return
    champ = max(t.teams.values(), key=lambda x: x.points)
    await client.send_message(cid,
        f"🏆 **TOURNAMENT CHAMPIONS!**\n\n"
        f"🥇 **{champ.name}** — {champ.points} pts!\n"
        f"Players: {', '.join(champ.players.values())}\n\n🎉 Congratulations!")
    await send_trophy_gif(client, cid, f"🏆 {champ.name} — Tournament Champions!")

@Client.on_message(filters.command("t_end") & filters.group)
async def cmd_t_end(client, msg: Message):
    t = tournaments.get(msg.chat.id)
    if not t: return await msg.reply("⚠️ No tournament!")
    if msg.from_user.id not in (t.host_id, Config.ADMIN_ID) and not await _is_admin(client, msg.chat.id, msg.from_user.id):
        return await msg.reply("🔒 Host or admin only!")
    del tournaments[msg.chat.id]
    await msg.reply("🛑 Tournament ended!")
