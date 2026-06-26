from pyrogram import Client, filters
from pyrogram.enums import ChatType
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from config import Config
from database.users import add_user, add_group
import utils.state as state
from plugins import solo

def start_text():
    n = state.bot_name.upper()
    return (
        f"🏏 **{n}** — Where legends are born\n\n"
        f"Real ball-by-ball cricket straight in your Telegram group.\n"
        f"No app. No drama. Pure cricket.\n\n"
        f"⚔️ **Modes:**\n"
        f"🧍 Solo — Every man for himself\n"
        f"👥 Team — Two sides, one champion\n"
        f"🏆 Tournament — `/tournament [teams] [size]`\n\n"
        f"Type `/help` for all commands!"
    )

ALL_COMMANDS = """
📋 **ALL COMMANDS**
━━━━━━━━━━━━━━━━━━━━

🧍 **SOLO MATCH**
/start — New match / mode choose
/join\\_solo — Join solo match
/leave\\_solo — Leave before start
/solo\\_score — Live scorecard
/solo\\_list — Joined players
/start\\_solo — Force start _(Admin)_
/extend\\_solo — +30s joining _(Admin)_
/end\\_solo — End match _(Admin)_

━━━━━━━━━━━━━━━━━━━━

👥 **TEAM MATCH**
/create\\_teams — Open team joining _(Host)_
/join\\_A — Join Team A
/join\\_B — Join Team B
/members\\_list — Show all players
/choose\\_caps — Set captains _(Host)_
/set\\_overs — Set overs _(Batting Cap)_
/batting — Choose batter _(Batting Cap)_
/bowling — Choose bowler _(Bowling Cap)_
/score — Live scorecard
/change\\_cap — Transfer captaincy _(Host)_
/end\\_match — End match _(Host/Admin)_

━━━━━━━━━━━━━━━━━━━━

🏆 **TOURNAMENT**
/tournament — Default 3 teams of 3
/tournament 4 5 — 4 teams, 5 players each
/t\\_join\\_A /t\\_join\\_B ... — Join teams
/t\\_start — Begin _(Host)_
/t\\_result A B A — Log result
/t\\_score — Standings
/t\\_end — End _(Host/Admin)_

━━━━━━━━━━━━━━━━━━━━

📊 **STATS**
/stats — Your stats
/stats @user — Anyone's stats
/leaderboard — Top players

━━━━━━━━━━━━━━━━━━━━

⚙️ **ADMIN**
/spamfree — Toggle spam-free _(Group Admin)_
/end\\_match — Force end any match _(Admin)_
/broadcast — Message all users _(Bot Owner)_
/maintenance on/off — _(Bot Owner)_
"""

def help_kb():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🏏 PlayZone", url=Config.PLAYZONE_LINK),
        InlineKeyboardButton("🆘 Support",  url=Config.SUPPORT_LINK),
    ]])

@Client.on_message(filters.command("start"))
async def cmd_start(client, msg: Message):
    user = msg.from_user
    is_pm = msg.chat.type == ChatType.PRIVATE
    await add_user(user.id, user.username or "", user.full_name)
    if not is_pm: await add_group(msg.chat.id, msg.chat.title)

    if state.maintenance_mode and user.id != Config.ADMIN_ID:
        return await msg.reply("🔧 **Maintenance Mode** — Bot is down for a bit. Come back soon!")

    if is_pm:
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("🏏 PlayZone", url=Config.PLAYZONE_LINK),
            InlineKeyboardButton("🆘 Support",  url=Config.SUPPORT_LINK),
        ],[
            InlineKeyboardButton("➕ Add to Group", url=f"https://t.me/{state.bot_username}?startgroup=true"),
        ]])
        await msg.reply(start_text(), reply_markup=kb)
    else:
        await solo.show_mode_menu(client, msg)

@Client.on_message(filters.command("help"))
async def cmd_help(client, msg: Message):
    # Send full command list directly in chat (like other bots)
    await msg.reply(ALL_COMMANDS, reply_markup=help_kb())
