from typing import List, Optional

def mention(uid: int, name: str) -> str:
    """Inline mention link — Pyrogram markdown renders this as a clickable @mention."""
    return f"[{name}](tg://user?id={uid})"

def sr(runs, balls):
    return round((runs / balls) * 100, 1) if balls > 0 else 0.0

def eco(runs, balls):
    overs = balls / 6
    return round(runs / overs, 1) if overs > 0 else 0.0

def bowl_keyboard():
    from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    import utils.state as state
    username = state.bot_username or "bot"
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🎯 Bowl in DM", url=f"https://t.me/{username}?start=bowl")
    ]])

# ── In-game prompts ───────────────────────────────────────────────────────────

def bat_prompt(batter_id: int, batter_name: str, ball_num: int, total_balls: int) -> str:
    return (
        f"🏏 **Ball {ball_num}/{total_balls}**\n"
        f"{mention(batter_id, batter_name)} — type your number **(0–6)** in the group!\n"
        f"⏱️ 60 seconds on the clock..."
    )

def bowl_prompt(bowler_id: int, bowler_name: str,
                ball_num: int, total_balls: int,
                over_num: int = 1, total_overs: int = 1) -> str:
    over_info = f" — Over {over_num}/{total_overs}" if total_overs > 1 else ""
    return (
        f"🎯 **Ball {ball_num}/{total_balls}{over_info}**\n"
        f"{mention(bowler_id, bowler_name)} — tap button & send secret number **(1–6)** in DM!\n"
        f"⏱️ 60 seconds remaining..."
    )

def dot_ball_msg(batter_id: int, batter_name: str) -> str:
    return f"⚫ **Dot Ball!** — {mention(batter_id, batter_name)} no run."

def century_msg(batter_id: int, batter_name: str, runs: int) -> str:
    if runs >= 100:
        return f"💯 **CENTURY!** {mention(batter_id, batter_name)} smashes **{runs}** — what a knock! 🔥"
    return f"🏅 **HALF-CENTURY!** {mention(batter_id, batter_name)} reaches **{runs}** — brilliant!"

def innings_break_msg(batting_team: str, score: int, wickets: int, target: int) -> str:
    return (
        f"🔄 **INNINGS BREAK!**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"**{batting_team}** scored **{score}/{wickets}**\n\n"
        f"🎯 Target: **{target}** runs\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )

# ── Scorecards ────────────────────────────────────────────────────────────────

def solo_scorecard(players_data: list, overs: int) -> str:
    lines = [
        "━━━━━━━━━━━━━━━━━━━━",
        f"🏏 **LIVE SCORECARD** — {overs} Balls/Player",
        "━━━━━━━━━━━━━━━━━━━━",
    ]
    for i, p in enumerate(players_data, 1):
        status  = "✅" if not p["is_out"] else "❌"
        log_str = " · ".join(str(b) for b in p["ball_log"]) if p["ball_log"] else "—"
        lines.append(
            f"{i}. {status} **{p['full_name']}**\n"
            f"┣ Runs: **{p['runs']}** ({p['balls']} balls)  SR: {sr(p['runs'], p['balls'])}\n"
            f"┣ Balls: {log_str}\n"
            f"┗ Wkts: {p['wickets']}  Eco: {eco(p['runs_given'], p['balls_bowled'])}"
        )
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)

def solo_result_card(players_data: list, overs: int,
                     best_batter: str, best_bowler: str, motm: str) -> str:
    sorted_p = sorted(players_data, key=lambda p: p["runs"], reverse=True)
    lines = [
        "🏆 **MATCH OVER — FINAL SCORECARD**",
        "━━━━━━━━━━━━━━━━━━━━",
    ]
    for i, p in enumerate(sorted_p, 1):
        status  = "✅" if not p["is_out"] else "❌"
        log_str = " · ".join(str(b) if b != "W" else "W" for b in p["ball_log"]) if p["ball_log"] else "—"
        lines.append(
            f"{i}. {status} **{p['full_name']}** — {p['runs']} runs ({p['balls']} balls)\n"
            f"┗ {log_str}"
        )
    lines += [
        "━━━━━━━━━━━━━━━━━━━━",
        f"🏆 **Best Batter:** {best_batter}",
        f"🎯 **Best Bowler:** {best_bowler}",
        f"⭐ **Player of the Match:** {motm}",
        "━━━━━━━━━━━━━━━━━━━━",
    ]
    return "\n".join(lines)

def team_scorecard(match) -> str:
    def team_block(team_dict, team_name, score, wickets):
        lines = [f"**{team_name}** — {score}/{wickets}"]
        for p in team_dict.values():
            status = "not out" if not p.is_out else "out"
            lines.append(f"  **{p.full_name}** {p.runs}({p.balls}) [{status}]")
        return "\n".join(lines)
    return (
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📊 **LIVE SCORECARD**\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        + team_block(match.team_a, "🔴 Team A", match.team_a_score, match.team_a_wickets) + "\n\n"
        + team_block(match.team_b, "🔵 Team B", match.team_b_score, match.team_b_wickets) + "\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )

def team_result_card(match, winner: str, motm_name: str) -> str:
    return (
        f"🏆 **MATCH OVER!**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🎉 **Winner:** {winner}\n\n"
        f"🔴 **Team A:** {match.team_a_score}/{match.team_a_wickets}\n"
        f"🔵 **Team B:** {match.team_b_score}/{match.team_b_wickets}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⭐ **Player of the Match:** {motm_name}\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )

def stats_card(user_name: str, s: dict) -> str:
    balls = s.get("balls_faced", 0)
    runs  = s.get("runs", 0)
    balled= s.get("balls_bowled", 0)
    wkts  = s.get("wickets_taken", 0)
    rc    = s.get("runs_conceded", 0)
    return (
        f"📊 **{user_name} — Stats**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏏 **Batting**\n"
        f"┣ Matches:       **{s.get('matches', 0)}**\n"
        f"┣ Runs:          **{runs}**  (SR: {sr(runs, balls)})\n"
        f"┣ Highest:       **{s.get('highest_score', 0)}**\n"
        f"┣ 100s / 50s:    **{s.get('centuries', 0)}** / **{s.get('half_centuries', 0)}**\n"
        f"┗ 4s / 6s:       **{s.get('fours', 0)}** / **{s.get('sixes', 0)}**\n\n"
        f"🎯 **Bowling**\n"
        f"┣ Wickets:       **{wkts}**\n"
        f"┣ Economy:       **{eco(rc, balled)}**\n"
        f"┗ Hat-Tricks:    **{s.get('hat_tricks', 0)}**\n\n"
        f"🏆 **Honours**\n"
        f"┣ Wins:          **{s.get('wins', 0)}**\n"
        f"┗ Player of Match: **{s.get('motm', 0)}**\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )

def leaderboard_card(title: str, players: list, key: str, label: str) -> str:
    medals = ["🥇", "🥈", "🥉"]
    lines  = [f"🏆 **{title}**", "━━━━━━━━━━━━━━━━━━━━"]
    for i, p in enumerate(players):
        medal = medals[i] if i < 3 else f"{i+1}."
        lines.append(f"{medal} **{p.get('full_name', 'Unknown')}** — {p.get(key, 0)} {label}")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)

def toss_msg(winner_name: str, choice: str) -> str:
    return (
        f"🪙 **TOSS!**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 **{winner_name}** wins the toss!\n"
        f"➡️ Chose to **{choice}** first.\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
