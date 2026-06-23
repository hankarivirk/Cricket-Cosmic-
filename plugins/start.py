from pyrogram import Client, filters
from pyrogram.enums import ChatType
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from config import Config
from database.users import add_user, add_group
import utils.state as state
from plugins import solo

# ── Dynamic text (uses bot_name detected at startup from the token) ──────────

def start_text() -> str:
    name = state.bot_name.upper()
    return (
        f"🏏 **{name}** — Where legends are born\n\n"
        f"🎙 Live the game. Feel the roar.\n\n"
        f"Real ball-by-ball cricket straight in your Telegram group.\n"
        f"No app needed. No drama. Pure cricket.\n\n"
        f"⚔️ **CHOOSE YOUR BATTLE**\n"
        f"┣ 👥 Team Match — Two sides. One champion.\n"
        f"┗ 🧍 Solo Match — Every man for himself.\n\n"
        f"🏆 **WHAT'S IN THE PITCH**\n"
        f"┣ 🎯 Live gameplay — ball by ball\n"
        f"┣ 📊 Scorecards that update in real-time\n"
        f"┣ 🪙 Toss, Overs, Captains\n"
        f"┣ 🎩 Hat-tricks and 💯 Century alerts\n"
        f"┗ 🏅 Player of the Match — you could be next\n\n"
        f"💥 Ready to play? Add me to your group and type /start\n\n"
        f"🔇 Psst — your group will never be the same again 😈"
    )

def help_text() -> str:
    return (
        f"📖 **{state.bot_name.upper()} — HELP**\n\n"
        f"Choose a game mode to get started 👇"
    )

SOLO_HELP = (
    "🧍 **SOLO MATCH — COMMANDS**\n\n"
    "`/start` — New match shuru karo\n"
    "`/join_solo` — Solo match join karo\n"
    "`/leave_solo` — Match se niklo (before start)\n"
    "`/solo_list` — Joined players dekho\n"
    "`/solo_score` — Live scorecard\n"
    "`/start_solo` — Force start (Group Admin)\n"
    "`/extend_solo` — Joining +30 sec (Group Admin)\n"
    "`/resume_solo` — Match resume (Group Admin)\n"
    "`/end_solo` — Match khatam karo (Group Admin)\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "🧍 **HOW TO PLAY — SOLO**\n\n"
    "🚀 `/start` → Solo Match → overs choose karo\n"
    "👥 Min **2**, Max **20** players\n"
    "🎯 Bowler — DM mein secret number bhejo (button tap karo)\n"
    "🏏 Batter — Group mein 1 to 6 type karo\n"
    "❌ Same number = **WICKET**\n"
    "✅ Different = **Runs** (batter's number counts)\n"
    "⚠️ Time out = auto OUT / dot ball penalty\n"
    "🏆 Highest scorer **WINS!**"
)

TEAM_HELP = (
    "👥 **TEAM MATCH — COMMANDS**\n\n"
    "`/start` — Match shuru karo (tu Host banega)\n"
    "`/host` — Current host kaun hai\n"
    "`/create_teams` — Team joining kholo (Host)\n"
    "`/recreate_teams` — Reset & reopen (Host)\n"
    "`/join_A` `/join_B` — Team join karo\n"
    "`/add_A` `/add_B` — Force add (Host)\n"
    "`/remove` — Player remove (Host)\n"
    "`/members_list` — Teams & players dekho\n"
    "`/choose_caps` — Captains select (Host)\n"
    "`/set_overs` — Overs set karo (Captain)\n"
    "`/batting` — Next batter choose (Captain)\n"
    "`/bowling` — Bowler choose (Captain)\n"
    "`/score` — Live scorecard\n"
    "`/change_host` — Host change vote\n"
    "`/change_cap` — Captaincy transfer (Host)\n"
    "`/end_match` — Match khatam (Host/Admin)\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "👥 **HOW TO PLAY — TEAM**\n\n"
    "🚀 `/start` → Team Match → Tu Host\n"
    "👥 `/create_teams` → Team A & B joining\n"
    "👑 `/choose_caps` → Captains select karo\n"
    "🪙 Toss automatic — coin flip!\n"
    "⚙️ Toss winner → Bat ya Bowl choose\n"
    "📏 Captain → `/set_overs`\n"
    "🎯 Bowler → DM mein secret number (button tap)\n"
    "🏏 Batter → Group mein 1–6 type karo\n"
    "❌ Same = WICKET  |  ✅ Different = Runs\n"
    "🔄 Innings change → Target chase!\n"
    "🏆 Higher score **WINS!**\n\n"
    "⚠️ Bowler must start the bot in DM at least once!"
)

TOURNAMENT_HELP = (
    "🏆 **TOURNAMENT MODE — HOW TO PLAY**\n\n"
    "🚀 `/tournament` — Default: 3 teams of 3\n"
    "🚀 `/tournament 4 5` — Custom: 4 teams, 5 players each\n"
    "👥 Teams auto-named: A, B, C, D...\n"
    "🎮 Round Robin — every team plays each other\n"
    "🏅 Finals: top 2 teams!\n\n"
    "**Commands:**\n"
    "`/tournament [teams] [size]` — Start tournament\n"
    "`/t_join_A` `/t_join_B` etc. — Team join\n"
    "`/t_start` — Tournament begin (Host)\n"
    "`/t_score` — Standings\n"
    "`/t_result A B A` — Log result: A beat B\n"
    "`/t_end` — End tournament (Host/Admin)"
)

STATS_HELP = (
    "📊 **STATS & LEADERBOARD**\n\n"
    "`/stats` — Apni stats dekho\n"
    "`/stats @username` — Kisi ki bhi stats\n"
    "`/leaderboard` — Top players list"
)

ADMIN_HELP = (
    "⚙️ **ADMIN COMMANDS**\n\n"
    "`/broadcast <msg>` — Sabko message bhejo\n"
    "`/users` — Total users & groups\n"
    "`/maintenance on/off` — Bot on/off\n"
    "`/end_match` — Koi bhi match force end\n"
    "`/reset_stats <user_id>` — Stats reset\n"
    "`/spamfree` — Toggle spam-free mode (per group)\n"
    "`/db_stats` — Database info"
)

def help_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🧍 Solo Match",  callback_data="help_solo"),
            InlineKeyboardButton("👥 Team Match",  callback_data="help_team"),
        ],[
            InlineKeyboardButton("🏆 Tournament",  callback_data="help_tournament"),
            InlineKeyboardButton("📊 Stats",        callback_data="help_stats"),
        ],[
            InlineKeyboardButton("⚙️ Admin",        callback_data="help_admin"),
        ],[
            InlineKeyboardButton("🏏 PlayZone",    url=Config.PLAYZONE_LINK),
            InlineKeyboardButton("🆘 Support",     url=Config.SUPPORT_LINK),
        ]
    ])

def back_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back", callback_data="help_main")]])

# ── Handlers ──────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("start"))
async def start_cmd(client: Client, message: Message):
    user       = message.from_user
    is_private = message.chat.type == ChatType.PRIVATE

    await add_user(user.id, user.username or "", user.full_name)
    if not is_private:
        await add_group(message.chat.id, message.chat.title)

    if state.maintenance_mode and user.id != Config.ADMIN_ID:
        return await message.reply(
            "🔧 **Maintenance Mode**\n\n"
            "Bot abhi maintenance par hai. Thodi der baad aana! 🙏"
        )

    if is_private:
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("🏏 PlayZone", url=Config.PLAYZONE_LINK),
            InlineKeyboardButton("🆘 Support",  url=Config.SUPPORT_LINK),
        ],[
            InlineKeyboardButton(
                "➕ Add me to your Group!",
                url=f"https://t.me/{state.bot_username}?startgroup=true"
            ),
        ]])
        await message.reply(start_text(), reply_markup=kb)
    else:
        await solo.show_mode_menu(client, message)

@Client.on_message(filters.command("help"))
async def help_cmd(client: Client, message: Message):
    await message.reply(help_text(), reply_markup=help_keyboard())

@Client.on_callback_query(filters.regex("^help_"))
async def help_callback(client: Client, cb: CallbackQuery):
    data = cb.data
    mapping = {
        "help_main":       (help_text(),      help_keyboard()),
        "help_solo":       (SOLO_HELP,         back_keyboard()),
        "help_team":       (TEAM_HELP,         back_keyboard()),
        "help_tournament": (TOURNAMENT_HELP,   back_keyboard()),
        "help_stats":      (STATS_HELP,        back_keyboard()),
    }
    if data == "help_admin":
        if cb.from_user.id != Config.ADMIN_ID:
            return await cb.answer("🔒 Sirf bot owner dekh sakta hai!", show_alert=True)
        await cb.message.edit_text(ADMIN_HELP, reply_markup=back_keyboard())
        return await cb.answer()

    if data in mapping:
        text, kb = mapping[data]
        await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()
