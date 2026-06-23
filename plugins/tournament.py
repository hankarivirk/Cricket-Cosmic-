import itertools
import string
from pyrogram import Client, filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import Message
from config import Config
from utils.state import tournaments, Tournament, TournamentTeam, GamePhase
from utils.gifs import send_trophy_gif

ADMIN_STATUSES  = (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
TEAM_LABELS     = list(string.ascii_uppercase)   # A, B, C … Z
MAX_TEAMS       = 8

@Client.on_message(filters.command("tournament") & filters.group)
async def tournament_start_cmd(client: Client, message: Message):
    chat_id = message.chat.id
    if chat_id in tournaments:
        return await message.reply("⚠️ Ek tournament already chal raha hai is group mein!")

    # ── Parse optional args: /tournament [num_teams] [team_size] ─────────────
    args      = message.command[1:]
    num_teams = 3
    team_size = 3
    try:
        if len(args) >= 1:
            num_teams = int(args[0])
        if len(args) >= 2:
            team_size = int(args[1])
    except ValueError:
        return await message.reply(
            "⚠️ Usage: `/tournament` or `/tournament <teams> <size>`\n"
            "Example: `/tournament 4 5` → 4 teams, 5 players each"
        )

    if not (2 <= num_teams <= MAX_TEAMS):
        return await message.reply(f"⚠️ Teams must be between 2 and {MAX_TEAMS}!")
    if not (1 <= team_size <= 20):
        return await message.reply("⚠️ Team size must be between 1 and 20!")

    t = Tournament(chat_id=chat_id, host_id=message.from_user.id,
                   team_size=team_size, phase=GamePhase.JOINING)

    labels = TEAM_LABELS[:num_teams]
    for label in labels:
        t.teams[label] = TournamentTeam(name=f"Team {label}")
    tournaments[chat_id] = t

    join_cmds = "  ".join(f"`/t_join_{k}`" for k in labels)
    await message.reply(
        f"🏆 **TOURNAMENT STARTED!**\n\n"
        f"👑 **Host:** {message.from_user.full_name}\n"
        f"🏟️ **Teams:** {num_teams}  |  👥 **Size:** {team_size} players/team\n\n"
        f"Join commands:\n{join_cmds}\n\n"
        f"Host types `/t_start` once all teams are filled.\n"
        f"Host can join too! 💪"
    )

async def _join_tournament_team(client, message: Message, team_key: str):
    t = tournaments.get(message.chat.id)
    if not t or t.phase != GamePhase.JOINING:
        return await message.reply("⚠️ No tournament joining open!")
    if team_key not in t.teams:
        return await message.reply(f"⚠️ Team {team_key} doesn't exist in this tournament!")

    user = message.from_user
    for key, team in t.teams.items():
        if user.id in team.players:
            return await message.reply(f"✅ Tu already **Team {key}** mein hai!")

    team = t.teams[team_key]
    if len(team.players) >= t.team_size:
        return await message.reply(f"⚠️ Team {team_key} full hai! (Max {t.team_size})")

    team.players[user.id] = user.full_name
    await message.reply(
        f"✅ **{user.full_name}** joined **Team {team_key}**! "
        f"({len(team.players)}/{t.team_size})"
    )

# ── Dynamic join handlers (A–H) ───────────────────────────────────────────────
for _label in TEAM_LABELS[:MAX_TEAMS]:
    def _make_handler(label):
        @Client.on_message(filters.command(f"t_join_{label}") & filters.group)
        async def _handler(client: Client, message: Message, _l=label):
            await _join_tournament_team(client, message, _l)
        _handler.__name__ = f"t_join_{label}_cmd"
        return _handler
    _make_handler(_label)

@Client.on_message(filters.command("t_score") & filters.group)
async def t_score_cmd(client: Client, message: Message):
    t = tournaments.get(message.chat.id)
    if not t:
        return await message.reply("⚠️ No active tournament!")

    lines = ["🏆 **TOURNAMENT STANDINGS**", "━━━━━━━━━━━━━━━━━━━━"]
    for i, team in enumerate(sorted(t.teams.values(), key=lambda x: x.points, reverse=True), 1):
        players = ", ".join(team.players.values()) or "—"
        lines.append(
            f"{i}. **{team.name}** — {team.points} pts ({team.wins} wins)\n"
            f"     Players: {players}"
        )
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    await message.reply("\n".join(lines))

@Client.on_message(filters.command("t_members") & filters.group)
async def t_members_cmd(client: Client, message: Message):
    t = tournaments.get(message.chat.id)
    if not t:
        return await message.reply("⚠️ No active tournament!")
    lines = [f"👥 **TOURNAMENT TEAMS** ({t.team_size} per team)", "━━━━━━━━━━━━━━━━━━━━"]
    for key, team in t.teams.items():
        names = "\n".join(f"  • {n}" for n in team.players.values()) or "  — (empty)"
        lines.append(f"**{team.name}** ({len(team.players)}/{t.team_size})\n{names}")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    await message.reply("\n".join(lines))

@Client.on_message(filters.command("t_start") & filters.group)
async def t_start_cmd(client: Client, message: Message):
    t = tournaments.get(message.chat.id)
    if not t or message.from_user.id != t.host_id:
        return await message.reply("🔒 Only the Host can start the tournament!")

    empty = [k for k, team in t.teams.items() if len(team.players) == 0]
    if empty:
        return await message.reply(
            f"⚠️ These teams have no players: {', '.join(empty)}\n"
            f"Add players or remove empty teams first."
        )

    keys     = list(t.teams.keys())
    fixtures = list(itertools.combinations(keys, 2))
    t.fixtures = fixtures
    t.phase    = GamePhase.WAITING

    fixture_text = "\n".join(
        f"  • {t.teams[a].name} 🆚 {t.teams[b].name}"
        for a, b in fixtures
    )
    await message.reply(
        f"🏆 **TOURNAMENT FIXTURES (Round Robin)**\n\n"
        f"{fixture_text}\n\n"
        f"Start each fixture using `/start` → Team Match.\n"
        f"Log results with `/t_result <A> <B> <winner>`\n"
        f"Example: `/t_result A B A` — Team A beat Team B\n\n"
        f"📊 Check standings: `/t_score`"
    )

@Client.on_message(filters.command("t_result") & filters.group)
async def t_result_cmd(client: Client, message: Message):
    t = tournaments.get(message.chat.id)
    if not t or message.from_user.id != t.host_id:
        return await message.reply("🔒 Only the Host can log results!")
    if len(message.command) < 4:
        return await message.reply("⚠️ Usage: `/t_result <TeamA> <TeamB> <Winner>`")

    t1, t2, winner = (x.upper() for x in message.command[1:4])
    if winner not in t.teams:
        return await message.reply("⚠️ Invalid winner — use team letters (A, B, C...)")

    t.teams[winner].wins   += 1
    t.teams[winner].points += 2
    t.results.append((t1, t2, winner))

    await message.reply(
        f"✅ **Result Logged!**\n\n"
        f"{t.teams.get(t1, type('', (), {'name': t1})()).name} 🆚 "
        f"{t.teams.get(t2, type('', (), {'name': t2})()).name} → "
        f"🏆 **{t.teams[winner].name}** wins!"
    )

    if len(t.results) >= len(t.fixtures):
        await _announce_winner(client, message.chat.id)

async def _announce_winner(client, chat_id):
    t = tournaments.get(chat_id)
    if not t:
        return
    champion = max(t.teams.values(), key=lambda x: x.points)
    await client.send_message(
        chat_id,
        f"🏆🏆🏆 **TOURNAMENT CHAMPIONS!** 🏆🏆🏆\n\n"
        f"🥇 **{champion.name}** — {champion.points} points!\n\n"
        f"Players: {', '.join(champion.players.values())}\n\n"
        f"🎉 Congratulations, legends! 🏏"
    )
    await send_trophy_gif(client, chat_id, f"🏆 {champion.name} are the Tournament Champions!")

@Client.on_message(filters.command("t_end") & filters.group)
async def t_end_cmd(client: Client, message: Message):
    t = tournaments.get(message.chat.id)
    if not t:
        return await message.reply("⚠️ No active tournament!")
    try:
        member   = await client.get_chat_member(message.chat.id, message.from_user.id)
        is_admin = member.status in ADMIN_STATUSES
    except Exception:
        is_admin = False
    if message.from_user.id not in (t.host_id, Config.ADMIN_ID) and not is_admin:
        return await message.reply("🔒 Only the Host or group admin can end the tournament!")
    del tournaments[message.chat.id]
    await message.reply("🛑 **Tournament ended!**")
