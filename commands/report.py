import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class Reports(commands.Cog):
    def __init__(self, bot, get_db_connection_func):
        self.bot = bot
        self.get_db_connection = get_db_connection_func
        self.report_schedules = []
        self.init_db_tables()
        self.load_report_schedules()
        self.check_scheduled_reports.start()

    def cog_unload(self):
        self.check_scheduled_reports.cancel()

    def init_db_tables(self):
        try:
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        # Table for scheduled reports
                        cur.execute("""
                            CREATE TABLE IF NOT EXISTS report_schedules (
                                id SERIAL PRIMARY KEY,
                                guild_id BIGINT NOT NULL,
                                channel_id BIGINT NOT NULL,
                                frequency TEXT CHECK (frequency IN ('daily', 'weekly')) NOT NULL,
                                last_sent TIMESTAMP,
                                is_active BOOLEAN DEFAULT TRUE,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                UNIQUE(guild_id, channel_id, frequency)
                            )
                        """)
                        conn.commit()
                    logger.info("✅ Reports tables initialized")
                else:
                    logger.warning("⚠️ Database connection not available - reports tables not initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize reports tables: {e}")

    def load_report_schedules(self):
        try:
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            SELECT id, guild_id, channel_id, frequency, last_sent, is_active
                            FROM report_schedules WHERE is_active = TRUE
                        """)
                        self.report_schedules = cur.fetchall()
            logger.info(f"✅ Loaded {len(self.report_schedules)} report schedules from DB")
        except Exception as e:
            logger.error(f"❌ Failed to load report schedules: {e}")

    @tasks.loop(minutes=10)
    async def check_scheduled_reports(self):
        now = datetime.utcnow()
        for schedule in self.report_schedules:
            schedule_id, guild_id, channel_id, frequency, last_sent, is_active = schedule
            if not is_active:
                continue
            send_report = False
            if frequency == 'daily':
                if not last_sent or (now - last_sent) >= timedelta(days=1):
                    send_report = True
            elif frequency == 'weekly':
                if not last_sent or (now - last_sent) >= timedelta(weeks=1):
                    send_report = True
            if send_report:
                guild = self.bot.get_guild(guild_id)
                if guild:
                    channel = guild.get_channel(channel_id)
                    if channel:
                        try:
                            if frequency == 'daily':
                                await self.report_daily(channel)
                            else:
                                await self.report_weekly(channel)
                            # Update last_sent
                            with self.get_db_connection() as conn:
                                if conn:
                                    with conn.cursor() as cur:
                                        cur.execute("""
                                            UPDATE report_schedules SET last_sent = %s WHERE id = %s
                                        """, (now, schedule_id))
                                        conn.commit()
                            # Update in-memory last_sent
                            schedule = (schedule_id, guild_id, channel_id, frequency, now, is_active)
                        except Exception as e:
                            logger.error(f"❌ Failed to send scheduled report {frequency} to {channel.id}: {e}")

    @check_scheduled_reports.before_loop
    async def before_check_scheduled_reports(self):
        await self.bot.wait_until_ready()

    @commands.hybrid_command(name="report_daily", description="Generate today's activity report")
    async def report_daily(self, ctx_or_channel):
        # ctx_or_channel can be Context or TextChannel
        channel = ctx_or_channel if isinstance(ctx_or_channel, discord.TextChannel) else ctx_or_channel.channel
        guild = channel.guild

        try:
            today = datetime.utcnow().date()
            with self.get_db_connection() as conn:
                if not conn:
                    await channel.send("❌ Database unavailable. Cannot generate report.")
                    return
                with conn.cursor() as cur:
                    # Sample query: count tasks completed today
                    cur.execute("""
                        SELECT COUNT(*) FROM team_tasks 
                        WHERE status = 'Done' AND created_at::date = %s AND guild_id = %s
                    """, (today, guild.id))
                    completed_tasks = cur.fetchone()[0]

                    # Sample query: sum coding time or commits could be fetched from another table
                    # Here, placeholders used
                    coding_time = 300  # in minutes
                    commits = 10  # number of commits
                    
            embed = discord.Embed(
                title=f"📅 Daily Activity Report - {today}",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Tasks Completed", value=str(completed_tasks), inline=True)
            embed.add_field(name="Coding Time (min)", value=str(coding_time), inline=True)
            embed.add_field(name="Commits", value=str(commits), inline=True)

            if not isinstance(ctx_or_channel, discord.TextChannel):
                await ctx_or_channel.send(embed=embed)
            else:
                await channel.send(embed=embed)
        except Exception as e:
            logger.error(f"❌ error generating daily report: {e}")
            if not isinstance(ctx_or_channel, discord.TextChannel):
                await ctx_or_channel.send("❌ Failed to generate daily report.", ephemeral=True)
            else:
                await channel.send("❌ Failed to generate daily report.")

    @commands.hybrid_command(name="report_weekly", description="Generate this week's summary report")
    async def report_weekly(self, ctx_or_channel):
        channel = ctx_or_channel if isinstance(ctx_or_channel, discord.TextChannel) else ctx_or_channel.channel
        guild = channel.guild

        try:
            today = datetime.utcnow().date()
            week_ago = today - timedelta(days=7)

            with self.get_db_connection() as conn:
                if not conn:
                    await channel.send("❌ Database unavailable. Cannot generate report.")
                    return
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT COUNT(*) FROM team_tasks 
                        WHERE status = 'Done' AND created_at::date BETWEEN %s AND %s AND guild_id = %s
                    """, (week_ago, today, guild.id))
                    completed_tasks = cur.fetchone()[0]

                    # sample coding time and commit placeholders
                    coding_time = 2100  # minutes
                    commits = 42
                    
            embed = discord.Embed(
                title=f"🗓️ Weekly Summary Report - {week_ago} to {today}",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Tasks Completed", value=str(completed_tasks), inline=True)
            embed.add_field(name="Coding Time (min)", value=str(coding_time), inline=True)
            embed.add_field(name="Commits", value=str(commits), inline=True)

            if not isinstance(ctx_or_channel, discord.TextChannel):
                await ctx_or_channel.send(embed=embed)
            else:
                await channel.send(embed=embed)
        except Exception as e:
            logger.error(f"❌ error generating weekly report: {e}")
            if not isinstance(ctx_or_channel, discord.TextChannel):
                await ctx_or_channel.send("❌ Failed to generate weekly report.", ephemeral=True)
            else:
                await channel.send("❌ Failed to generate weekly report.")

    @commands.hybrid_command(name="report_personal", description="Generate your personal activity report")
    @app_commands.describe(period="daily or weekly")
    async def report_personal(self, ctx, period: Optional[str] = "daily"):
        channel = ctx.channel
        user_id = ctx.author.id
        guild = ctx.guild

        try:
            today = datetime.utcnow().date()
            if period == "daily":
                start_date = today
            elif period == "weekly":
                start_date = today - timedelta(days=7)
            else:
                await ctx.send("❌ Invalid period. Use 'daily' or 'weekly'.", ephemeral=True)
                return

            with self.get_db_connection() as conn:
                if not conn:
                    await ctx.send("❌ Database unavailable. Cannot generate report.", ephemeral=True)
                    return
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT COUNT(*) FROM team_tasks
                        WHERE status = 'Done' AND creator_id = %s AND created_at::date >= %s AND guild_id = %s
                    """, (user_id, start_date, guild.id))
                    completed_tasks = cur.fetchone()[0]

                    # Placeholders for coding time and commits
                    coding_time = 180
                    commits = 7
                    
            embed = discord.Embed(
                title=f"🧍 Personal {period.capitalize()} Activity Report",
                color=discord.Color.teal(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Tasks Completed", value=str(completed_tasks), inline=True)
            embed.add_field(name="Coding Time (min)", value=str(coding_time), inline=True)
            embed.add_field(name="Commits", value=str(commits), inline=True)

            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"❌ error generating personal report: {e}")
            await ctx.send("❌ Failed to generate personal report.", ephemeral=True)

    @commands.hybrid_command(name="report_team", description="Generate team-wide report")
    @app_commands.describe(period="daily or weekly")
    async def report_team(self, ctx, period: Optional[str] = "daily"):
        channel = ctx.channel
        guild = ctx.guild

        try:
            today = datetime.utcnow().date()
            if period == "daily":
                start_date = today
            elif period == "weekly":
                start_date = today - timedelta(days=7)
            else:
                await ctx.send("❌ Invalid period. Use 'daily' or 'weekly'.", ephemeral=True)
                return

            with self.get_db_connection() as conn:
                if not conn:
                    await ctx.send("❌ Database unavailable. Cannot generate report.", ephemeral=True)
                    return
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT COUNT(*) FROM team_tasks
                        WHERE status = 'Done' AND created_at::date >= %s AND guild_id = %s
                    """, (start_date, guild.id))
                    completed_tasks = cur.fetchone()[0]

                    # Placeholder for coding time and commits
                    coding_time = 1500
                    commits = 30
                    
            embed = discord.Embed(
                title=f"👥 Team {period.capitalize()} Report",
                color=discord.Color.dark_teal(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Tasks Completed", value=str(completed_tasks), inline=True)
            embed.add_field(name="Coding Time (min)", value=str(coding_time), inline=True)
            embed.add_field(name="Commits", value=str(commits), inline=True)

            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"❌ error generating team report: {e}")
            await ctx.send("❌ Failed to generate team report.", ephemeral=True)

    @commands.hybrid_command(name="report_schedule", description="Schedule automatic reports")
    @app_commands.describe(
        frequency="Frequency to send reports (daily or weekly)",
        channel="Channel to send reports in"
    )
    async def report_schedule(self, ctx: commands.Context, frequency: str, channel: discord.TextChannel):
        frequency = frequency.lower()
        if frequency not in ("daily", "weekly"):
            await ctx.send("❌ Frequency must be 'daily' or 'weekly'.", ephemeral=True)
            return
        
        try:
            with self.get_db_connection() as conn:
                if not conn:
                    await ctx.send("❌ Database unavailable. Cannot schedule report.", ephemeral=True)
                    return
                with conn.cursor() as cur:
                    # Insert or update schedule
                    cur.execute("""
                        INSERT INTO report_schedules (guild_id, channel_id, frequency, is_active, last_sent)
                        VALUES (%s, %s, %s, TRUE, NULL)
                        ON CONFLICT (guild_id, channel_id, frequency) DO UPDATE
                        SET is_active = TRUE
                    """, (ctx.guild.id, channel.id, frequency))
                    conn.commit()
            self.load_report_schedules()
            embed = discord.Embed(
                title="⏰ Report Scheduled",
                description=f"Automatic {frequency} reports will be sent in {channel.mention}",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"❌ error scheduling report: {e}")
            await ctx.send("❌ Failed to schedule report.", ephemeral=True)

async def setup(bot: commands.Bot):
    get_db_connection_func = getattr(bot, "get_db_connection", None)
    if not get_db_connection_func:
        logger.error("❌ get_db_connection not found on bot instance")
        return
    await bot.add_cog(Reports(bot, get_db_connection_func))
    logger.info("✅ Reports cog loaded successfully")
