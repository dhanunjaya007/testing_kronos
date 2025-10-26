import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class ProgressTracking(commands.Cog):
    def __init__(self, bot, get_db_connection_func):
        self.bot = bot
        self.get_db_connection = get_db_connection_func
        self.blockers = {}
        self.blocker_counter = 0
        self.load_blockers()

    def load_blockers(self):
        try:
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT blocker_id, description FROM blockers WHERE resolved = FALSE")
                        rows = cur.fetchall()
                        self.blockers = {row[0]: {'description': row[1], 'resolved': False} for row in rows}
                        self.blocker_counter = max([int(bid[1:]) for bid in self.blockers.keys()], default=0)
            logger.info(f"✅ Loaded {len(self.blockers)} active blockers")
        except Exception as e:
            logger.error(f"❌ Failed to load blockers: {e}")

    @commands.hybrid_command(name="progress_daily", description="View today's team progress")
    async def progress_daily(self, ctx: commands.Context):
        today = datetime.utcnow().date()
        try:
            with self.get_db_connection() as conn:
                if not conn:
                    await ctx.send("❌ Database unavailable.")
                    return
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT COUNT(*) FROM team_tasks 
                        WHERE status = 'Done' AND created_at::date = %s AND guild_id = %s
                    """, (today, ctx.guild.id))
                    tasks_completed = cur.fetchone()[0]
                    # Additional real data fetch can be added here, e.g., coding time, commits
            embed = discord.Embed(
                title=f"📈 Daily Team Progress - {today}",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Tasks Completed", value=str(tasks_completed))
            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"❌ progress_daily command failed: {e}")
            await ctx.send("❌ Failed to fetch daily progress.")

    @commands.hybrid_command(name="progress_weekly", description="View weekly team progress summary")
    async def progress_weekly(self, ctx: commands.Context):
        today = datetime.utcnow().date()
        week_start = today - timedelta(days=7)
        try:
            with self.get_db_connection() as conn:
                if not conn:
                    await ctx.send("❌ Database unavailable.")
                    return
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT COUNT(*) FROM team_tasks 
                        WHERE status = 'Done' AND created_at::date BETWEEN %s AND %s AND guild_id = %s
                    """, (week_start, today, ctx.guild.id))
                    tasks_completed = cur.fetchone()[0]
            embed = discord.Embed(
                title=f"📊 Weekly Team Progress - {week_start} to {today}",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Tasks Completed", value=str(tasks_completed))
            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"❌ progress_weekly command failed: {e}")
            await ctx.send("❌ Failed to fetch weekly progress.")

    @commands.hybrid_command(name="progress_milestone", description="Check milestone completion percentage")
    @app_commands.describe(milestone_id="Milestone ID")
    async def progress_milestone(self, ctx: commands.Context, milestone_id: str):
        try:
            with self.get_db_connection() as conn:
                if not conn:
                    await ctx.send("❌ Database unavailable.")
                    return
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT progress, title FROM milestones WHERE milestone_id = %s
                    """, (milestone_id,))
                    row = cur.fetchone()
            if not row:
                await ctx.send(f"❌ Milestone {milestone_id} not found.")
                return
            progress, title = row
            embed = discord.Embed(
                title=f"🎯 Milestone: {title}",
                color=discord.Color.gold()
            )
            embed.add_field(name="Completion %", value=f"{progress}%")
            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"❌ progress_milestone command failed: {e}")
            await ctx.send("❌ Failed to fetch milestone progress.")

    @commands.hybrid_command(name="progress_user", description="View specific user's progress")
    @app_commands.describe(user="User to view progress for")
    async def progress_user(self, ctx: commands.Context, user: Optional[discord.Member] = None):
        target = user or ctx.author
        try:
            with self.get_db_connection() as conn:
                if not conn:
                    await ctx.send("❌ Database unavailable.")
                    return
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT COUNT(*) FROM team_tasks 
                        WHERE status = 'Done' AND assignee_id = %s AND guild_id = %s
                    """, (target.id, ctx.guild.id))
                    tasks_completed = cur.fetchone()[0]
            embed = discord.Embed(
                title=f"👤 Progress for {target.display_name}",
                color=discord.Color.blue()
            )
            embed.add_field(name="Tasks Completed", value=str(tasks_completed))
            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"❌ progress_user command failed: {e}")
            await ctx.send("❌ Failed to fetch user progress.")

    @commands.hybrid_command(name="progress_chart", description="Generate progress visualization chart")
    @app_commands.describe(period="Period for progress (daily, weekly, monthly)")
    async def progress_chart(self, ctx: commands.Context, period: Optional[str] = "daily"):
        # Placeholder for actual chart generation logic
        await ctx.send(f"📊 Progress chart generation for {period} is under construction.")

    @commands.hybrid_command(name="blockers_add", description="Report a blocker/issue")
    @app_commands.describe(description="Describe the blocker")
    async def blockers_add(self, ctx: commands.Context, *, description: str):
        try:
            self.blocker_counter += 1
            blocker_id = f"B{self.blocker_counter}"
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO blockers (blocker_id, description, resolved)
                            VALUES (%s, %s, FALSE)
                        """, (blocker_id, description))
                        conn.commit()
                    self.blockers[blocker_id] = {'description': description, 'resolved': False}
            embed = discord.Embed(
                title=f"🚧 Blocker {blocker_id} added",
                description=description,
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"❌ blockers_add command failed: {e}")
            await ctx.send("❌ Failed to add blocker.")

    @commands.hybrid_command(name="blockers_list", description="View all active blockers")
    async def blockers_list(self, ctx: commands.Context):
        if not self.blockers:
            await ctx.send("ℹ️ No active blockers found.")
            return
        embed = discord.Embed(
            title="🚧 Active Blockers",
            color=discord.Color.orange()
        )
        for blocker_id, data in self.blockers.items():
            embed.add_field(name=blocker_id, value=data['description'], inline=False)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="blockers_resolve", description="Mark blocker as resolved")
    @app_commands.describe(blocker_id="Blocker ID to resolve")
    async def blockers_resolve(self, ctx: commands.Context, blocker_id: str):
        blocker_id = blocker_id.upper()
        if blocker_id not in self.blockers:
            await ctx.send(f"❌ Blocker {blocker_id} not found.")
            return
        try:
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("UPDATE blockers SET resolved = TRUE WHERE blocker_id = %s", (blocker_id,))
                        conn.commit()
                    del self.blockers[blocker_id]
            await ctx.send(f"✅ Blocker {blocker_id} marked as resolved.")
        except Exception as e:
            logger.error(f"❌ blockers_resolve command failed: {e}")
            await ctx.send("❌ Failed to resolve blocker.")

async def setup(bot: commands.Bot):
    get_db_connection_func = getattr(bot, "get_db_connection", None)
    if not get_db_connection_func:
        logger.error("❌ get_db_connection not found on bot instance")
        return
    await bot.add_cog(ProgressTracking(bot, get_db_connection_func))
    logger.info("✅ ProgressTracking cog loaded successfully")
