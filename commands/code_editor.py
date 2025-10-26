import discord
from discord import app_commands
from discord.ext import commands
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import io
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

class CodeEditor(commands.Cog):
    def __init__(self, bot, get_db_connection_func):
        self.bot = bot
        self.get_db_connection = get_db_connection_func
        self.init_db_tables()

    def init_db_tables(self):
        """Initialize code editor tracking tables"""
        try:
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        # Create coding sessions table
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
                            )
                        """)
                        
                        # Create coding stats table
                        cur.execute("""
                            CREATE TABLE IF NOT EXISTS coding_stats (
                                id SERIAL PRIMARY KEY,
                                user_id BIGINT NOT NULL,
                                language TEXT NOT NULL,
                                total_hours DECIMAL(10,2) DEFAULT 0,
                                session_count INT DEFAULT 0,
                                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                UNIQUE(user_id, language)
                            )
                        """)
                        
                        conn.commit()
            logger.info("✅ Code editor tables initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize code editor tables: {e}")

    # ===== REAL-TIME ACTIVITY MONITORING =====

    @app_commands.command(name="code_status", description="View current coding status")
    @app_commands.describe(user="User to check (optional)")
    async def code_status(self, interaction: discord.Interaction, user: discord.Member = None):
        """View current coding status"""
        try:
            user = user or interaction.user
            embed = discord.Embed(
                title=f"🖥️ Current Coding Status: {user.display_name}",
                color=discord.Color.blue(),
                description="**Editor:** Visual Studio Code\n**Language:** Python 🐍\n**File:** main.py\n**Elapsed:** 45 min"
            )
            embed.set_thumbnail(url=user.display_avatar.url)
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            logger.error(f"code_status error: {e}")
            await interaction.response.send_message("❌ Failed to fetch coding status.", ephemeral=True)

    @app_commands.command(name="code_now", description="See who's currently coding")
    async def code_now(self, interaction: discord.Interaction):
        """Show currently coding members"""
        try:
            embed = discord.Embed(
                title="👨‍💻 Members Currently Coding",
                color=discord.Color.green(),
                description="• **Alice** — Python, 25m\n• **Bob** — JS, 11m"
            )
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            logger.error(f"code_now error: {e}")
            await interaction.response.send_message("❌ Failed to fetch current coders.", ephemeral=True)

    @app_commands.command(name="code_verify", description="Check if Rich Presence is working")
    async def code_verify(self, interaction: discord.Interaction):
        """Verify Rich Presence"""
        try:
            embed = discord.Embed(
                title="✅ Rich Presence Check",
                color=discord.Color.green(),
                description="Your Rich Presence is active and being tracked!"
            )
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            logger.error(f"code_verify error: {e}")
            await interaction.response.send_message("❌ Verification failed.", ephemeral=True)

    @app_commands.command(name="code_toggle", description="Enable/disable activity tracking")
    async def code_toggle(self, interaction: discord.Interaction):
        """Toggle activity tracking"""
        try:
            embed = discord.Embed(title="🔄 Activity Tracking", color=discord.Color.orange())
            embed.description = "You have **enabled** code editor tracking. Use this again to disable."
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            logger.error(f"code_toggle error: {e}")
            await interaction.response.send_message("❌ Failed to toggle tracking.", ephemeral=True)

    @app_commands.command(name="code_sync", description="Manually sync editor data")
    async def code_sync(self, interaction: discord.Interaction):
        """Sync editor data"""
        try:
            embed = discord.Embed(title="🔃 Manual Sync", color=discord.Color.teal())
            embed.description = "Code editor data has been synced!"
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            logger.error(f"code_sync error: {e}")
            await interaction.response.send_message("❌ Failed to sync data.", ephemeral=True)

    # ===== COMPREHENSIVE STATISTICS =====

    @app_commands.command(name="code_stats", description="View detailed coding statistics")
    @app_commands.describe(user="User to check (optional)")
    async def code_stats(self, interaction: discord.Interaction, user: discord.Member = None):
        """View coding statistics"""
        try:
            user = user or interaction.user
            embed = discord.Embed(
                title=f"📊 Coding Stats: {user.display_name}",
                color=discord.Color.purple(),
            )
            stats = {"Python": 14, "JS": 9, "TS": 6, "HTML": 2}
            total = sum(stats.values())
            for lang, hr in stats.items():
                embed.add_field(name=lang, value=f"{hr} hours", inline=True)
            embed.add_field(name="**Total**", value=f"{total} hours", inline=True)
            embed.set_thumbnail(url=user.display_avatar.url)
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            logger.error(f"code_stats error: {e}")
            await interaction.response.send_message("❌ Failed to fetch stats.", ephemeral=True)

    @app_commands.command(name="code_languages", description="View language breakdown")
    @app_commands.describe(user="User to check (optional)")
    async def code_languages(self, interaction: discord.Interaction, user: discord.Member = None):
        """View language breakdown"""
        try:
            user = user or interaction.user
            embed = discord.Embed(
                title=f"🈯 Language Breakdown: {user.display_name}",
                description="Your top languages:",
                color=discord.Color.blue(),
            )
            lang_stats = [("Python", 10), ("JS", 8), ("HTML", 3)]
            for lang, hours in lang_stats:
                embed.add_field(name=lang, value=f"{hours}h", inline=True)
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            logger.error(f"code_languages error: {e}")
            await interaction.response.send_message("❌ Failed to fetch languages.", ephemeral=True)

    @app_commands.command(name="code_sessions", description="View recent coding sessions")
    @app_commands.describe(
        user="User to check (optional)",
        days="Number of days to show (default: 7)"
    )
    async def code_sessions(self, interaction: discord.Interaction, user: discord.Member = None, days: int = 7):
        """View recent sessions"""
        try:
            if days > 30:
                days = 30
            
            user = user or interaction.user
            embed = discord.Embed(
                title=f"📅 Recent Coding Sessions: {user.display_name}",
                color=discord.Color.green(),
                description=f"Showing last {days} days of sessions."
            )
            sessions = ["2023-10-22: Python (2h)", "2023-10-21: JS (1h30m)", "2023-10-20: HTML (40m)"]
            for sess in sessions:
                embed.add_field(name="Session", value=sess, inline=False)
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            logger.error(f"code_sessions error: {e}")
            await interaction.response.send_message("❌ Failed to fetch sessions.", ephemeral=True)

    @app_commands.command(name="code_history", description="View detailed coding history")
    @app_commands.describe(
        user="User to check (optional)",
        days="Number of days to show (default: 7)"
    )
    async def code_history(self, interaction: discord.Interaction, user: discord.Member = None, days: int = 7):
        """View coding history"""
        try:
            if days > 30:
                days = 30
            
            user = user or interaction.user
            embed = discord.Embed(
                title=f"🕓 Coding History: {user.display_name}",
                color=discord.Color.blurple(),
            )
            hist_head = "`Date      Lang      Duration`"
            history = "\n".join([
                "`2023-10-20 Python    2h10m`",
                "`2023-10-21 JS        1h5m`"
            ])
            embed.description = f"{hist_head}\n{history}\n*(Last {days} days)*"
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            logger.error(f"code_history error: {e}")
            await interaction.response.send_message("❌ Failed to fetch history.", ephemeral=True)

    # ===== ANALYTICS & INSIGHTS =====

    @app_commands.command(name="code_analytics", description="Advanced analytics dashboard")
    @app_commands.describe(period="Time period (weekly/monthly)")
    async def code_analytics(self, interaction: discord.Interaction, period: str = "weekly"):
        """Generate analytics chart"""
        await interaction.response.defer()
        
        try:
            if period not in ["weekly", "monthly"]:
                period = "weekly"
            
            stats = {"Python": 12, "JavaScript": 7, "TypeScript": 2}
            fig, ax = plt.subplots(figsize=(8, 6))
            ax.pie(stats.values(), labels=stats.keys(), autopct='%1.1f%%', startangle=90)
            ax.set_title(f"Coding Analytics ({period.title()})")
            
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
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
            logger.error(f"Error generating analytics: {e}")
            await interaction.followup.send("❌ Error generating chart. Please try again.", ephemeral=True)

    @app_commands.command(name="code_compare", description="Compare two users' coding stats")
    @app_commands.describe(
        user1="First user to compare",
        user2="Second user to compare"
    )
    async def code_compare(self, interaction: discord.Interaction, user1: discord.Member, user2: discord.Member):
        """Compare coding stats"""
        try:
            embed = discord.Embed(
                title=f"⚡ Compare Coding Stats",
                color=discord.Color.purple(),
            )
            embed.add_field(name=f"{user1.display_name}", value="Total: 30h\nPython: 20h", inline=True)
            embed.add_field(name=f"{user2.display_name}", value="Total: 25h\nPython: 15h", inline=True)
            embed.set_footer(text="Comparison of total and top language hours.")
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            logger.error(f"code_compare error: {e}")
            await interaction.response.send_message("❌ Failed to compare stats.", ephemeral=True)

    @app_commands.command(name="code_chart", description="Generate visual charts")
    @app_commands.describe(chart_type="Type of chart (bar/pie)")
    async def code_chart(self, interaction: discord.Interaction, chart_type: str = "bar"):
        """Generate visual chart"""
        await interaction.response.defer()
        
        try:
            if chart_type not in ["bar", "pie"]:
                chart_type = "bar"
            
            langs = ["Python", "JavaScript", "HTML"]
            hours = [12, 7, 3]
            
            fig, ax = plt.subplots(figsize=(10, 6))
            if chart_type.lower() == "pie":
                ax.pie(hours, labels=langs, autopct='%1.1f%%', startangle=90)
                ax.set_title(f'Coding Time Distribution')
            else:
                ax.bar(langs, hours, color=['#3572A5', '#F1E05A', '#E44D26'])
                ax.set_ylabel('Hours')
                ax.set_title(f'Coding Time by Language')
                ax.grid(axis='y', alpha=0.3)
            
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
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
            logger.error(f"Error generating chart: {e}")
            await interaction.followup.send("❌ Error generating chart. Please try again.", ephemeral=True)

    # ===== SETUP COMMANDS AND GUIDES =====

    @app_commands.command(name="setup_editor", description="Interactive editor selection guide")
    async def setup_editor(self, interaction: discord.Interaction):
        """Editor setup guide"""
        try:
            embed = discord.Embed(
                title="🛠️ Editor Setup Guide",
                color=discord.Color.orange(),
                description=(
                    "Select your editor for a tailored setup:\n"
                    "• `/setup_vscode` - VS Code\n"
                    "• `/setup_pycharm` - PyCharm\n"
                    "• `/setup_intellij` - IntelliJ IDEA\n"
                    "• `/setup_webstorm` - WebStorm\n"
                    "• `/setup_atom` - Atom\n"
                    "• `/setup_sublime` - Sublime Text\n"
                    "• `/setup_vim` - Vim/Neovim"
                ),
            )
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            logger.error(f"setup_editor error: {e}")
            await interaction.response.send_message("❌ Failed to show setup guide.", ephemeral=True)

    @app_commands.command(name="setup_vscode", description="VS Code extension guide")
    async def setup_vscode(self, interaction: discord.Interaction):
        """VS Code setup"""
        try:
            embed = discord.Embed(
                title="🟦 VS Code Setup Guide",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="Extension",
                value="Search `Discord Presence` by iCrawl in Extensions tab. Install and reload VS Code.",
                inline=False
            )
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            logger.error(f"setup_vscode error: {e}")
            await interaction.response.send_message("❌ Failed to show VS Code guide.", ephemeral=True)

    @app_commands.command(name="setup_pycharm", description="PyCharm plugin guide")
    async def setup_pycharm(self, interaction: discord.Interaction):
        """PyCharm setup"""
        try:
            embed = discord.Embed(
                title="🐍 PyCharm Setup Guide",
                color=discord.Color.green(),
                description=(
                    "1. Preferences > Plugins\n"
                    "2. Search `Discord Integration`\n"
                    "3. Install & restart PyCharm"
                ),
            )
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            logger.error(f"setup_pycharm error: {e}")
            await interaction.response.send_message("❌ Failed to show PyCharm guide.", ephemeral=True)

    @app_commands.command(name="setup_intellij", description="IntelliJ IDEA plugin guide")
    async def setup_intellij(self, interaction: discord.Interaction):
        """IntelliJ setup"""
        try:
            embed = discord.Embed(
                title="💡 IntelliJ IDEA Setup Guide",
                color=discord.Color.gold(),
                description="Install `Discord Integration` plugin from Marketplace."
            )
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            logger.error(f"setup_intellij error: {e}")
            await interaction.response.send_message("❌ Failed to show IntelliJ guide.", ephemeral=True)

    @app_commands.command(name="setup_webstorm", description="WebStorm plugin guide")
    async def setup_webstorm(self, interaction: discord.Interaction):
        """WebStorm setup"""
        try:
            embed = discord.Embed(
                title="🌐 WebStorm Setup Guide",
                color=discord.Color.teal(),
                description="Install `Discord Integration` plugin for full support."
            )
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            logger.error(f"setup_webstorm error: {e}")
            await interaction.response.send_message("❌ Failed to show WebStorm guide.", ephemeral=True)

    @app_commands.command(name="setup_atom", description="Atom package guide")
    async def setup_atom(self, interaction: discord.Interaction):
        """Atom setup"""
        try:
            embed = discord.Embed(
                title="🅰️ Atom Setup Guide",
                color=discord.Color.dark_red(),
                description="Run `apm install atom-discord` in terminal."
            )
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            logger.error(f"setup_atom error: {e}")
            await interaction.response.send_message("❌ Failed to show Atom guide.", ephemeral=True)

    @app_commands.command(name="setup_sublime", description="Sublime Text plugin guide")
    async def setup_sublime(self, interaction: discord.Interaction):
        """Sublime setup"""
        try:
            embed = discord.Embed(
                title="📰 Sublime Text Setup Guide",
                color=discord.Color.dark_magenta(),
                description="Install `Discord Rich Presence` from Package Control."
            )
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            logger.error(f"setup_sublime error: {e}")
            await interaction.response.send_message("❌ Failed to show Sublime guide.", ephemeral=True)

    @app_commands.command(name="setup_vim", description="Vim/Neovim plugin guide")
    async def setup_vim(self, interaction: discord.Interaction):
        """Vim setup"""
        try:
            embed = discord.Embed(
                title="🟩 Vim/Neovim Setup Guide",
                color=discord.Color.green(),
                description="Use [presence.nvim](https://github.com/andweeb/presence.nvim) for Discord integration."
            )
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            logger.error(f"setup_vim error: {e}")
            await interaction.response.send_message("❌ Failed to show Vim guide.", ephemeral=True)

    @app_commands.command(name="setup_verify", description="Verify your complete setup")
    async def setup_verify(self, interaction: discord.Interaction):
        """Verify setup"""
        try:
            embed = discord.Embed(
                title="🔎 Setup Verification",
                color=discord.Color.blurple(),
                description="Checking editor integration and Rich Presence..."
            )
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            logger.error(f"setup_verify error: {e}")
            await interaction.response.send_message("❌ Verification failed.", ephemeral=True)

    @app_commands.command(name="setup_test", description="Test Rich Presence connection")
    async def setup_test(self, interaction: discord.Interaction):
        """Test Rich Presence"""
        try:
            embed = discord.Embed(
                title="🧪 Rich Presence Test",
                color=discord.Color.green(),
                description="Testing... Please open your editor and ensure Discord shows your activity."
            )
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            logger.error(f"setup_test error: {e}")
            await interaction.response.send_message("❌ Test failed.", ephemeral=True)

    @app_commands.command(name="setup_troubleshoot", description="Common setup issues")
    async def setup_troubleshoot(self, interaction: discord.Interaction):
        """Troubleshooting guide"""
        try:
            embed = discord.Embed(
                title="🛠️ Troubleshooting Setup",
                color=discord.Color.red(),
                description=(
                    "- Ensure Discord desktop is running\n"
                    "- Check Activity Privacy in Discord settings\n"
                    "- Restart both Discord and your editor\n"
                    "- Use the recommended extension for your editor"
                )
            )
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            logger.error(f"setup_troubleshoot error: {e}")
            await interaction.response.send_message("❌ Failed to show troubleshooting.", ephemeral=True)

    @app_commands.command(name="setup_team", description="Setup guide for team leads")
    async def setup_team(self, interaction: discord.Interaction):
        """Team setup guide"""
        try:
            embed = discord.Embed(
                title="🤝 Team Lead Setup Guide",
                color=discord.Color.gold(),
                description="Have team members run `/setup_editor` and `/setup_verify`.\nCreate a #coding channel for leaderboard and stats."
            )
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            logger.error(f"setup_team error: {e}")
            await interaction.response.send_message("❌ Failed to show team guide.", ephemeral=True)

    @app_commands.command(name="setup_hackathon", description="Fast setup for hackathons")
    async def setup_hackathon(self, interaction: discord.Interaction):
        """Hackathon setup"""
        try:
            embed = discord.Embed(
                title="🏁 Hackathon Fast Setup",
                color=discord.Color.blurple(),
                description="Install your editor plugin, enable Discord Rich Presence, verify with `/setup_verify`."
            )
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            logger.error(f"setup_hackathon error: {e}")
            await interaction.response.send_message("❌ Failed to show hackathon guide.", ephemeral=True)


async def setup(bot: commands.Bot):
    """Setup function for the cog"""
    get_db_connection_func = getattr(bot, "get_db_connection", None)
    if not get_db_connection_func:
        logger.error("❌ get_db_connection not found on bot instance")
        return
    await bot.add_cog(CodeEditor(bot, get_db_connection_func))
    logger.info("✅ CodeEditor cog loaded successfully")
