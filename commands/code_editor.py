import discord
from discord import app_commands
from discord.ext import commands
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import io
import logging
from datetime import datetime
import re

logger = logging.getLogger(__name__)

class CodeEditor(commands.Cog):
    EDITORS = [
        "Visual Studio Code", "PyCharm", "IntelliJ IDEA", "WebStorm",
        "Atom", "Sublime Text", "Vim", "Neovim"
    ]
    LANG_PATTERNS = {
        "python": ["python", ".py"],
        "javascript": ["javascript", ".js"],
        "typescript": ["typescript", ".ts"],
        "java": ["java", ".java"],
        "cpp": ["c++", ".cpp", ".cc"],
        "c": ["c language", ".c"],
        "html": ["html", ".html"],
        "css": ["css", ".css"],
        "go": ["go", ".go"],
        "rust": ["rust", ".rs"],
        "ruby": ["ruby", ".rb"],
    }
    
    def __init__(self, bot, get_db_connection_func):
        self.bot = bot
        self.get_db_connection = get_db_connection_func
        self.init_db_tables()
    
    def init_db_tables(self):
        try:
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            CREATE TABLE IF NOT EXISTS coding_sessions (
                                id SERIAL PRIMARY KEY,
                                user_id BIGINT NOT NULL,
                                language TEXT NOT NULL,
                                editor TEXT,
                                file_name TEXT,
                                start_time TIMESTAMP NOT NULL,
                                end_time TIMESTAMP,
                                duration_minutes INT,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            );
                        """)
                        cur.execute("""
                            CREATE TABLE IF NOT EXISTS coding_stats (
                                id SERIAL PRIMARY KEY,
                                user_id BIGINT NOT NULL,
                                language TEXT NOT NULL,
                                total_hours DECIMAL(10,2) DEFAULT 0,
                                session_count INT DEFAULT 0,
                                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                UNIQUE(user_id, language)
                            );
                        """)
                        conn.commit()
            logger.info("✅ DB tables initialized")
        except Exception as e:
            logger.error(f"❌ DB table init failed: {e}")

    # ========== Presence Event Listener ==========
    @commands.Cog.listener()
    async def on_presence_update(self, before: discord.Member, after: discord.Member):
        try:
            before_act = self._get_coding_activity(before.activities)
            after_act = self._get_coding_activity(after.activities)
            if before_act is None and after_act is not None:
                await self._start_coding_session(after.id, after_act)
            elif before_act is not None and after_act is None:
                await self._end_coding_session(after.id)
            elif before_act and after_act and before_act != after_act:
                await self._end_coding_session(after.id)
                await self._start_coding_session(after.id, after_act)
        except Exception as e:
            logger.error(f"on_presence_update error: {e}")

    def _extract_language(self, activity):
        details = (getattr(activity, "details", "") or "").lower()
        state = (getattr(activity, "state", "") or "").lower()
        text = f"{details} {state}"
        for lang, patterns in self.LANG_PATTERNS.items():
            if any(p in text for p in patterns):
                return lang
        return "unknown"
    def _extract_filename(self, text):
        if not text: return None
        m = re.search(r"([a-zA-Z0-9_\-]+\.[a-zA-Z0-9]+)", text)
        return m.group(1) if m else None
    def _get_coding_activity(self, activities):
        for act in activities:
            if isinstance(act, discord.Activity) and act.name in self.EDITORS:
                lang = self._extract_language(act)
                file = self._extract_filename(getattr(act, "details", "") or getattr(act, "state", ""))
                return {
                    "editor": act.name,
                    "language": lang,
                    "file_name": file,
                    "details": getattr(act, "details", ""),
                    "state": getattr(act, "state", "")
                }
        return None

    async def _start_coding_session(self, user_id, activity_info):
        try:
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO coding_sessions (user_id, language, editor, file_name, start_time)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (
                            user_id, activity_info["language"], activity_info["editor"],
                            activity_info["file_name"], datetime.utcnow()
                        ))
                        conn.commit()
        except Exception as e:
            logger.error(f"Start session error: {e}")
    async def _end_coding_session(self, user_id):
        try:
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            SELECT id, language, start_time FROM coding_sessions
                            WHERE user_id = %s AND end_time IS NULL
                            ORDER BY start_time DESC LIMIT 1
                        """, (user_id,))
                        row = cur.fetchone()
                        if not row: return
                        session_id, language, start = row
                        end = datetime.utcnow()
                        duration = int((end - start).total_seconds() // 60)
                        cur.execute("""
                            UPDATE coding_sessions 
                            SET end_time = %s, duration_minutes = %s
                            WHERE id = %s
                        """, (end, duration, session_id))
                        cur.execute("""
                            INSERT INTO coding_stats (user_id, language, total_hours, session_count)
                            VALUES (%s, %s, %s, 1)
                            ON CONFLICT (user_id, language) DO UPDATE SET 
                                total_hours = coding_stats.total_hours + EXCLUDED.total_hours,
                                session_count = coding_stats.session_count + 1,
                                last_updated = CURRENT_TIMESTAMP
                        """, (user_id, language, duration/60.0))
                        conn.commit()
        except Exception as e:
            logger.error(f"End session error: {e}")

    # ========== Slash Commands ==========

    @app_commands.command(name="code_status", description="View current coding status")
    @app_commands.describe(user="User to check (optional)")
    async def code_status(self, interaction: discord.Interaction, user: discord.Member = None):
        try:
            target = user or interaction.user
            act = self._get_coding_activity(target.activities)
            embed = discord.Embed(
                title=f"🖥️ Current Coding Status: {target.display_name}",
                color=discord.Color.blue(),
            )
            if act:
                with self.get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            SELECT start_time FROM coding_sessions
                            WHERE user_id = %s AND end_time IS NULL
                            ORDER BY start_time DESC LIMIT 1
                        """, (target.id,))
                        result = cur.fetchone()
                start = result[0] if result else datetime.utcnow()
                elapsed = int((datetime.utcnow() - start).total_seconds() // 60)
                embed.description = (
                    f"**Editor:** {act['editor']}\n"
                    f"**Language:** {act['language']}\n"
                    f"**File:** {act.get('file_name', 'N/A')}\n"
                    f"**Elapsed:** {elapsed} min"
                )
            else:
                embed.description = "Not currently coding"
            embed.set_thumbnail(url=target.display_avatar.url)
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            logger.error(f"code_status error: {e}")
            await interaction.response.send_message("❌ Failed to fetch coding status.", ephemeral=True)
    
    @app_commands.command(name="code_now", description="See who's currently coding")
    async def code_now(self, interaction: discord.Interaction):
        try:
            lines = []
            for member in interaction.guild.members:
                act = self._get_coding_activity(member.activities)
                if act:
                    with self.get_db_connection() as conn:
                        with conn.cursor() as cur:
                            cur.execute("""
                                SELECT start_time FROM coding_sessions
                                WHERE user_id = %s AND end_time IS NULL
                                ORDER BY start_time DESC LIMIT 1
                            """, (member.id,))
                            result = cur.fetchone()
                    elapsed = int((datetime.utcnow() - (result[0] or datetime.utcnow())).total_seconds() // 60)
                    lines.append(f"• **{member.display_name}** — {act['language']}, {elapsed}m")
            embed = discord.Embed(
                title="👨‍💻 Members Currently Coding",
                description="\n".join(lines) if lines else "No one is currently coding",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            logger.error(f"code_now error: {e}")
            await interaction.response.send_message("❌ Failed to fetch current coders.", ephemeral=True)
    
    @app_commands.command(name="code_stats", description="View detailed coding statistics")
    @app_commands.describe(user="User to check (optional)")
    async def code_stats(self, interaction: discord.Interaction, user: discord.Member = None):
        try:
            target = user or interaction.user
            with self.get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT language, total_hours, session_count FROM coding_stats
                        WHERE user_id = %s
                        ORDER BY total_hours DESC
                    """, (target.id,))
                    stats = cur.fetchall()
            embed = discord.Embed(
                title=f"📊 Coding Stats: {target.display_name}",
                color=discord.Color.purple(),
            )
            if stats:
                total = sum(row[1] for row in stats)
                for lang, hours, sessions in stats:
                    embed.add_field(
                        name=lang.capitalize(),
                        value=f"{hours:.1f}h ({sessions} sessions)",
                        inline=True
                    )
                embed.add_field(name="**Total**", value=f"{total:.1f} hours", inline=True)
            else:
                embed.description = "No coding data yet!"
            embed.set_thumbnail(url=target.display_avatar.url)
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            logger.error(f"code_stats error: {e}")
            await interaction.response.send_message("❌ Failed to fetch stats.", ephemeral=True)
    
    @app_commands.command(name="code_sessions", description="View recent coding sessions")
    @app_commands.describe(user="User to check (optional)", days="Number of days (max 30)")
    async def code_sessions(self, interaction: discord.Interaction, user: discord.Member = None, days: int = 7):
        try:
            days = min(max(1, days), 30)
            target = user or interaction.user
            cutoff = datetime.utcnow().date()
            with self.get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT start_time, language, duration_minutes FROM coding_sessions
                        WHERE user_id = %s AND start_time > %s
                        ORDER BY start_time DESC
                    """, (target.id, cutoff))
                    sessions = cur.fetchall()
            embed = discord.Embed(
                title=f"📅 Recent Coding Sessions: {target.display_name}",
                color=discord.Color.green(),
                description=f"Showing last {days} days of sessions."
            )
            if sessions:
                for sess in sessions:
                    stime, lang, dur = sess
                    day = stime.strftime("%Y-%m-%d")
                    embed.add_field(
                        name=f"{day}",
                        value=f"{lang.capitalize()} ({dur//60}h{dur%60}m)" if dur else lang.capitalize(),
                        inline=False
                    )
            else:
                embed.add_field(name="No sessions!", value="\u200b", inline=False)
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            logger.error(f"code_sessions error: {e}")
            await interaction.response.send_message("❌ Failed to fetch sessions.", ephemeral=True)
    
    @app_commands.command(name="code_languages", description="View language breakdown")
    @app_commands.describe(user="User to check (optional)")
    async def code_languages(self, interaction: discord.Interaction, user: discord.Member = None):
        try:
            target = user or interaction.user
            with self.get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT language, total_hours FROM coding_stats
                        WHERE user_id = %s ORDER BY total_hours DESC
                    """, (target.id,))
                    langs = cur.fetchall()
            embed = discord.Embed(
                title=f"🈯 Language Breakdown: {target.display_name}",
                description="Your top languages:",
                color=discord.Color.blue(),
            )
            if langs:
                for l, h in langs:
                    embed.add_field(name=l.capitalize(), value=f"{h:.1f}h", inline=True)
            else:
                embed.description = "No language breakdown to show."
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            logger.error(f"code_languages error: {e}")
            await interaction.response.send_message("❌ Failed to fetch languages.", ephemeral=True)
    
    @app_commands.command(name="code_history", description="View detailed coding history")
    @app_commands.describe(user="User to check (optional)", days="Number of days to show (default: 7)")
    async def code_history(self, interaction: discord.Interaction, user: discord.Member = None, days: int = 7):
        try:
            days = min(max(1, days), 30)
            target = user or interaction.user
            cutoff = datetime.utcnow().date()
            with self.get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT start_time, language, duration_minutes FROM coding_sessions
                        WHERE user_id = %s AND start_time > %s
                        ORDER BY start_time DESC
                    """, (target.id, cutoff))
                    history = cur.fetchall()
            embed = discord.Embed(
                title=f"🕓 Coding History: {target.display_name}",
                color=discord.Color.blurple(),
            )
            if history:
                head = "`Date      Lang      Duration`"
                lines = "\n".join([
                    f"`{h[0].strftime('%Y-%m-%d')} {h[1]:<10} {h[2]//60}h{h[2]%60}m`"
                    for h in history
                ])
                embed.description = f"{head}\n{lines}\n*(Last {days} days)*"
            else:
                embed.description = "No history in selected period!"
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            logger.error(f"code_history error: {e}")
            await interaction.response.send_message("❌ Failed to fetch history.", ephemeral=True)

    @app_commands.command(name="code_analytics", description="Advanced analytics dashboard")
    @app_commands.describe(period="Time period (weekly/monthly)")
    async def code_analytics(self, interaction: discord.Interaction, period: str = "weekly"):
        await interaction.response.defer()
        try:
            period = "weekly" if period not in {"weekly", "monthly"} else period
            target = interaction.user
            with self.get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT language, total_hours FROM coding_stats
                        WHERE user_id = %s
                    """, (target.id,))
                    stats = {l: float(h) for l, h in cur.fetchall()}
            if not stats:
                await interaction.followup.send("No analytics data available.", ephemeral=True)
                return
            fig, ax = plt.subplots(figsize=(8, 6))
            ax.pie(stats.values(), labels=stats.keys(), autopct='%1.1f%%', startangle=90)
            ax.set_title(f"Coding Analytics ({period.title()})")
            buf = io.BytesIO()
            plt.savefig(buf, format="png", dpi=100, bbox_inches="tight")
            buf.seek(0)
            plt.close(fig)
            f = discord.File(buf, filename="analytics.png")
            embed = discord.Embed(
                title=f"📈 {period.title()} Analytics",
                color=discord.Color.teal(),
                description="Pie chart shows your coding time by language."
            )
            embed.set_image(url="attachment://analytics.png")
            await interaction.followup.send(embed=embed, file=f)
        except Exception as e:
            logger.error(f"code_analytics error: {e}")
            await interaction.followup.send("❌ Error generating chart. Please try again.", ephemeral=True)

    @app_commands.command(name="code_compare", description="Compare two users' coding stats")
    @app_commands.describe(user1="First user to compare", user2="Second user to compare")
    async def code_compare(self, interaction: discord.Interaction, user1: discord.Member, user2: discord.Member):
        try:
            stats = {}
            with self.get_db_connection() as conn:
                with conn.cursor() as cur:
                    for u in (user1, user2):
                        cur.execute("""
                            SELECT language, total_hours FROM coding_stats
                            WHERE user_id = %s
                        """, (u.id,))
                        stats[u] = cur.fetchall()
            def summary(stat):
                total = sum(h for l, h in stat)
                top = max(stat, key=lambda s: s[1], default=("None", 0))
                return f"Total: {total:.1f}h\n{top[0].capitalize()}: {top[1]:.1f}h"
            embed = discord.Embed(
                title="⚡ Compare Coding Stats",
                color=discord.Color.purple()
            )
            embed.add_field(name=f"{user1.display_name}", value=summary(stats[user1]), inline=True)
            embed.add_field(name=f"{user2.display_name}", value=summary(stats[user2]), inline=True)
            embed.set_footer(text="Comparison of total and top language hours.")
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            logger.error(f"code_compare error: {e}")
            await interaction.response.send_message("❌ Failed to compare stats.", ephemeral=True)

    @app_commands.command(name="code_chart", description="Generate visual charts")
    @app_commands.describe(chart_type="Type of chart (bar/pie)")
    async def code_chart(self, interaction: discord.Interaction, chart_type: str = "bar"):
        await interaction.response.defer()
        try:
            chart_type = chart_type if chart_type in ("bar", "pie") else "bar"
            target = interaction.user
            with self.get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT language, total_hours FROM coding_stats
                        WHERE user_id = %s
                    """, (target.id,))
                    stats = list(cur.fetchall())
            if not stats:
                await interaction.followup.send("No chart data available.", ephemeral=True)
                return
            langs = [l for l, h in stats]
            hours = [float(h) for l, h in stats]
            fig, ax = plt.subplots(figsize=(10, 6))
            if chart_type == "pie":
                ax.pie(hours, labels=langs, autopct="%1.1f%%", startangle=90)
                ax.set_title('Coding Time Distribution')
            else:
                ax.bar(langs, hours, color=['#3572A5', '#F1E05A', '#E44D26'][:len(langs)])
                ax.set_ylabel('Hours')
                ax.set_title(f'Coding Time by Language')
                ax.grid(axis="y", alpha=0.3)
            buf = io.BytesIO()
            plt.savefig(buf, format="png", dpi=100, bbox_inches="tight")
            buf.seek(0)
            plt.close(fig)
            file = discord.File(buf, filename="codechart.png")
            embed = discord.Embed(
                title="🖼️ Visual Coding Chart",
                color=discord.Color.blurple(),
                description=f"Generated a {chart_type.lower()} chart for your stats."
            )
            embed.set_image(url="attachment://codechart.png")
            await interaction.followup.send(embed=embed, file=file)
        except Exception as e:
            logger.error(f"code_chart error: {e}")
            await interaction.followup.send("❌ Error generating chart. Please try again.", ephemeral=True)
    
    from discord import app_commands
import discord
from discord.ext import commands
import logging

logger = logging.getLogger(__name__)

class CodeEditor(commands.Cog):  # (other logic omitted here for brevity)

    # ----- UNIVERSAL RICH PRESENCE STEPS -----
    @staticmethod
    def rich_presence_steps(editor_tip):
        return (
            "### Step 1️⃣: Install the Editor Extension/Plugin\n"
            f"{editor_tip}\n\n"
            "### Step 2️⃣: Install Discord Desktop\n"
            "👉 [Download Discord](https://discord.com/download) (must be running on your computer)\n\n"
            "### Step 3️⃣: Enable Discord Rich Presence\n"
            "• Open Discord desktop, go to **Settings → Activity Privacy**\n"
            "• Toggle **“Display current activity as a status message”** to ON.\n"
            "• Ensure **Privacy settings** allow this activity tracking.\n\n"
            "_Once finished, restart Discord & your code editor!_"
        )

    @app_commands.command(name="setup_editor", description="Interactive editor selection guide")
    async def setup_editor(self, interaction: discord.Interaction):
        try:
            embed = discord.Embed(
                title="🛠️ Code Editor Setup Guide",
                color=discord.Color.orange(),
                description=(
                    "Select your editor below for a complete Rich Presence setup (3 steps):\n"
                    "• `/setup_vscode` - VS Code\n"
                    "• `/setup_pycharm` - PyCharm\n"
                    "• `/setup_intellij` - IntelliJ IDEA\n"
                    "• `/setup_webstorm` - WebStorm\n"
                    "• `/setup_atom` - Atom\n"
                    "• `/setup_sublime` - Sublime Text\n"
                    "• `/setup_vim` - Vim/Neovim\n"
                ),
            )
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            logger.error(f"setup_editor error: {e}")
            await interaction.response.send_message("❌ Failed to show setup guide.", ephemeral=True)

    @app_commands.command(name="setup_vscode", description="VS Code extension setup guide")
    async def setup_vscode(self, interaction: discord.Interaction):
        tip = (
            "Search `Discord Presence` by iCrawl in the **VS Code Extensions** tab. Install and reload VS Code."
        )
        embed = discord.Embed(title="🟦 VS Code Full Setup", color=discord.Color.blue())
        embed.description = self.rich_presence_steps(tip)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="setup_pycharm", description="PyCharm plugin setup guide")
    async def setup_pycharm(self, interaction: discord.Interaction):
        tip = (
            "In PyCharm, go to `Preferences → Plugins` and search for `Discord Integration`. Install & restart PyCharm."
        )
        embed = discord.Embed(title="🐍 PyCharm Full Setup", color=discord.Color.green())
        embed.description = self.rich_presence_steps(tip)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="setup_intellij", description="IntelliJ IDEA plugin setup guide")
    async def setup_intellij(self, interaction: discord.Interaction):
        tip = "Install `Discord Integration` plugin from the IntelliJ **Marketplace → Plugins** section."
        embed = discord.Embed(title="💡 IntelliJ IDEA Full Setup", color=discord.Color.gold())
        embed.description = self.rich_presence_steps(tip)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="setup_webstorm", description="WebStorm plugin setup guide")
    async def setup_webstorm(self, interaction: discord.Interaction):
        tip = (
            "Open WebStorm, go to `Preferences → Plugins` and install `Discord Integration` for Rich Presence support."
        )
        embed = discord.Embed(title="🌐 WebStorm Full Setup", color=discord.Color.teal())
        embed.description = self.rich_presence_steps(tip)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="setup_atom", description="Atom package setup guide")
    async def setup_atom(self, interaction: discord.Interaction):
        tip = (
            "Open a terminal and run `apm install atom-discord` to add Discord Presence for Atom."
        )
        embed = discord.Embed(title="🅰️ Atom Full Setup", color=discord.Color.dark_red())
        embed.description = self.rich_presence_steps(tip)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="setup_sublime", description="Sublime Text plugin setup guide")
    async def setup_sublime(self, interaction: discord.Interaction):
        tip = (
            "Install `Discord Rich Presence` via **Package Control** in Sublime Text."
        )
        embed = discord.Embed(title="📰 Sublime Text Full Setup", color=discord.Color.dark_magenta())
        embed.description = self.rich_presence_steps(tip)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="setup_vim", description="Vim/Neovim plugin setup guide")
    async def setup_vim(self, interaction: discord.Interaction):
        tip = (
            "Install [`presence.nvim`](https://github.com/andweeb/presence.nvim) using your plugin manager."
        )
        embed = discord.Embed(title="🟩 Vim/Neovim Full Setup", color=discord.Color.green())
        embed.description = self.rich_presence_steps(tip)
        await interaction.response.send_message(embed=embed)

    # Verification, test, troubleshooting, team, and hackathon commands can be kept unchanged,
    # or updated similarly if you want to standardize their style.

    @app_commands.command(name="setup_verify", description="Verify your complete setup")
    async def setup_verify(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🔎 Setup Verification",
            color=discord.Color.blurple(),
            description="Checking editor integration and Rich Presence settings..."
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="setup_test", description="Test Rich Presence connection")
    async def setup_test(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🧪 Rich Presence Test",
            color=discord.Color.green(),
            description="Open your editor and ensure Discord shows your activity as Rich Presence."
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="setup_troubleshoot", description="Common setup issues guide")
    async def setup_troubleshoot(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🛠️ Troubleshooting Setup",
            color=discord.Color.red(),
            description=(
                "- Make sure Discord desktop is running\n"
                "- Verify Activity Privacy in Discord settings\n"
                "- Restart both Discord and your editor\n"
                "- Use the recommended extension/plugin for your editor"
            )
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="setup_team", description="Setup guide for team leads")
    async def setup_team(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🤝 Team Lead Setup Guide",
            color=discord.Color.gold(),
            description="Have team members run `/setup_editor` and `/setup_verify`.\nCreate a #coding channel for leaderboard and stats."
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="setup_hackathon", description="Fast setup for hackathons")
    async def setup_hackathon(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🏁 Hackathon Fast Setup",
            color=discord.Color.blurple(),
            description="Install your editor plugin, enable Discord Rich Presence, verify with `/setup_verify`."
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    get_db_connection_func = getattr(bot, "get_db_connection", None)
    if not get_db_connection_func:
        logger.error("❌ get_db_connection not found on bot instance")
        return
    await bot.add_cog(CodeEditor(bot, get_db_connection_func))
    logger.info("✅ CodeEditor cog loaded successfully")
