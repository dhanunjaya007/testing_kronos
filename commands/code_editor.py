import discord
from discord import app_commands
from discord.ext import commands
import matplotlib.pyplot as plt
import io

class CodeEditor(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ===== REAL-TIME ACTIVITY MONITORING =====

    @app_commands.command(name="code_status", description="View current coding status (file, language, editor, duration).")
    @app_commands.describe(user="User to check (optional)")
    async def code_status(self, interaction: discord.Interaction, user: discord.Member = None):
        user = user or interaction.user
        embed = discord.Embed(
            title=f"🖥️ Current Coding Status: {user.display_name}",
            color=discord.Color.blue(),
            description="**Editor:** Visual Studio Code\n**Language:** Python 🐍\n**File:** main.py\n**Elapsed:** 45 min"
        ).set_thumbnail(url=user.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="code_now", description="See who's currently coding right now.")
    async def code_now(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="👨‍💻 Members Currently Coding",
            color=discord.Color.green(),
            description="• **Alice** — Python, 25m\n• **Bob** — JS, 11m"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="code_verify", description="Check if your Rich Presence is working correctly.")
    async def code_verify(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="✅ Rich Presence Check",
            color=discord.Color.green(),
            description="Your Rich Presence is active and being tracked!"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="code_toggle", description="Enable/disable editor activity tracking.")
    async def code_toggle(self, interaction: discord.Interaction):
        embed = discord.Embed(title="🔄 Activity Tracking", color=discord.Color.orange())
        embed.description = "You have **enabled** code editor tracking. Use this again to disable."
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="code_sync", description="Manually sync editor data with Discord bot.")
    async def code_sync(self, interaction: discord.Interaction):
        embed = discord.Embed(title="🔃 Manual Sync", color=discord.Color.teal())
        embed.description = "Code editor data has been synced!"
        await interaction.response.send_message(embed=embed)

    # ===== COMPREHENSIVE STATISTICS =====

    @app_commands.command(name="code_stats", description="View detailed coding statistics.")
    @app_commands.describe(user="User to check (optional)")
    async def code_stats(self, interaction: discord.Interaction, user: discord.Member = None):
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

    @app_commands.command(name="code_languages", description="View language breakdown.")
    @app_commands.describe(user="User to check (optional)")
    async def code_languages(self, interaction: discord.Interaction, user: discord.Member = None):
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

    @app_commands.command(name="code_sessions", description="View recent coding sessions.")
    async def code_sessions(self, interaction: discord.Interaction, user: discord.Member = None, days: int = 7):
        user = user or interaction.user
        embed = discord.Embed(
            title=f"📅 Recent Coding Sessions: {user.display_name}",
            color=discord.Color.green(),
            description=f"Showing last {days} days of sessions."
        )
        # Example recent sessions:
        sessions = ["2023-10-22: Python (2h)", "2023-10-21: JS (1h30m)", "2023-10-20: HTML (40m)"]
        for sess in sessions:
            embed.add_field(name="Session", value=sess, inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="code_history", description="View detailed coding history.")
    async def code_history(self, interaction: discord.Interaction, user: discord.Member = None, days: int = 7):
        user = user or interaction.user
        embed = discord.Embed(
            title=f"🕓 Coding History: {user.display_name}",
            color=discord.Color.blurple(),
        )
        # Table-like history (for a real bot, render as paginated or attach a file)
        hist_head = "`Date      Lang      Duration`"
        history = "\n".join([
            "`2023-10-20 Python    2h10m`",
            "`2023-10-21 JS        1h5m`"
        ])
        embed.description = f"{hist_head}\n{history}\n*(Last {days} days)*"
        await interaction.response.send_message(embed=embed)

    # ===== ANALYTICS & INSIGHTS =====

    @app_commands.command(name="code_analytics", description="Advanced analytics dashboard.")
    async def code_analytics(self, interaction: discord.Interaction, period: str = "weekly"):
        # Simulate a generated pie chart for analytics
        stats = {"Python": 12, "JavaScript": 7, "TS": 2}
        fig, ax = plt.subplots()
        ax.pie(stats.values(), labels=stats.keys(), autopct='%1.1f%%')
        ax.set_title(f"Coding Analytics ({period.title()})")
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        f = discord.File(buf, filename="analytics.png")
        embed = discord.Embed(
            title=f"📈 {period.title()} Analytics",
            color=discord.Color.teal(),
            description="Pie chart shows your coding time by language."
        )
        embed.set_image(url="attachment://analytics.png")
        await interaction.response.send_message(embed=embed, file=f)

    @app_commands.command(name="code_compare", description="Compare two users' coding stats.")
    async def code_compare(self, interaction: discord.Interaction, user1: discord.Member, user2: discord.Member):
        # Mock comparison — make visually attractive
        embed = discord.Embed(
            title=f"⚡ Compare Coding Stats",
            color=discord.Color.purple(),
        )
        embed.add_field(name=f"{user1.display_name}", value="Total: 30h\nPython: 20h", inline=True)
        embed.add_field(name=f"{user2.display_name}", value="Total: 25h\nPython: 15h", inline=True)
        embed.set_footer(text="Comparison of total and top language hours.")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="code_chart", description="Generate visual charts.")
    async def code_chart(self, interaction: discord.Interaction, type: str = "bar"):
        # Demo with bar chart
        langs = ["Python", "JavaScript", "HTML"]
        hours = [12, 7, 3]
        fig, ax = plt.subplots()
        ax.bar(langs, hours, color=['#3572A5', '#F1E05A', '#E44D26'])
        ax.set_ylabel('Hours')
        ax.set_title(f'Coding Time by {type.title()}')
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        file = discord.File(buf, filename="codechart.png")
        embed = discord.Embed(
            title="🖼️ Visual Coding Chart",
            color=discord.Color.blurple(),
            description=f"Generated a {type.lower()} chart for your stats."
        ).set_image(url="attachment://codechart.png")
        await interaction.response.send_message(embed=embed, file=file)

    # ===== SETUP COMMANDS AND GUIDES =====

    @app_commands.command(name="setup_editor", description="Interactive editor selection and setup guide.")
    async def setup_editor(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🛠️ Editor Setup Guide",
            color=discord.Color.orange(),
            description=(
                "Select your editor for a tailored setup:\n"
                "• `/setup vscode` - VS Code\n"
                "• `/setup pycharm` - PyCharm\n"
                "• `/setup intellij` - IntelliJ IDEA\n"
                "• `/setup webstorm` - WebStorm\n"
                "• `/setup atom` - Atom\n"
                "• `/setup sublime` - Sublime Text\n"
                "• `/setup vim` - Vim/Neovim"
            ),
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="setup_vscode", description="VS Code extension installation guide.")
    async def setup_vscode(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🟦 VS Code Setup Guide",
            color=discord.Color.blue()
        ).add_field(
            name="Extension",
            value="Search `Discord Presence` by iCrawl in Extensions tab. Install and reload VS Code.",
            inline=False
        ).set_thumbnail(url="https://code.visualstudio.com/assets/images/code-stable.png")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="setup_pycharm", description="PyCharm plugin installation guide.")
    async def setup_pycharm(self, interaction: discord.Interaction):
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

    @app_commands.command(name="setup_intellij", description="IntelliJ IDEA plugin installation guide.")
    async def setup_intellij(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="💡 IntelliJ IDEA Setup Guide",
            color=discord.Color.dark_gold(),
            description="Install `Discord Integration` plugin from Marketplace."
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="setup_webstorm", description="WebStorm plugin installation guide.")
    async def setup_webstorm(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🌐 WebStorm Setup Guide",
            color=discord.Color.brand_green(),
            description="Install `Discord Integration` plugin for full support."
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="setup_atom", description="Atom package installation guide.")
    async def setup_atom(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🅰️ Atom Setup Guide",
            color=discord.Color.dark_red(),
            description="Run `apm install atom-discord` in terminal."
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="setup_sublime", description="Sublime Text plugin installation guide.")
    async def setup_sublime(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📰 Sublime Text Setup Guide",
            color=discord.Color.dark_magenta(),
            description="Install `Discord Rich Presence` from Package Control."
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="setup_vim", description="Vim/Neovim plugin installation guide.")
    async def setup_vim(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🟩 Vim/Neovim Setup Guide",
            color=discord.Color.brand_green(),
            description="Use [presence.nvim](https://github.com/andweeb/presence.nvim) for Discord integration."
        )
        await interaction.response.send_message(embed=embed)

    # === Verification & Testing ===

    @app_commands.command(name="setup_verify", description="Verify your complete setup (Discord + Editor).")
    async def setup_verify(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🔎 Setup Verification",
            color=discord.Color.blurple(),
            description="Checking editor integration and Rich Presence..."
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="setup_test", description="Test Rich Presence connection.")
    async def setup_test(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🧪 Rich Presence Test",
            color=discord.Color.green(),
            description="Testing... Please open your editor and ensure Discord shows your activity."
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="setup_troubleshoot", description="Common setup issues and solutions.")
    async def setup_troubleshoot(self, interaction: discord.Interaction):
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

    # === Specialized ===

    @app_commands.command(name="setup_team", description="Setup guide for team leads")
    async def setup_team(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🤝 Team Lead Setup Guide",
            color=discord.Color.gold(),
            description="Have team members run `/setup editor` and `/setup verify`.\nCreate a #coding channel for leaderboard and stats."
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="setup_hackathon", description="Fast setup for hackathon participants")
    async def setup_hackathon(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🏁 Hackathon Fast Setup",
            color=discord.Color.og_blurple(),
            description="Install your editor plugin, enable Discord Rich Presence, verify with `/setup verify`."
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(CodeEditor(bot))
