import discord
from discord import app_commands
from discord.ext import commands, tasks
import logging
from datetime import datetime
import asyncio
from typing import Optional

logger = logging.getLogger(__name__)

class Standup(commands.Cog):
    """Daily standup and pair programming commands for Discord"""

    def __init__(self, bot, get_db_connection_func):
        self.bot = bot
        self.get_db_connection = get_db_connection_func
        self.standup_schedules = []
        self.init_db_tables()
        self.check_scheduled_standups.start()
        # Will load schedules after wait_until_ready, below
        asyncio.create_task(self.load_standup_schedules())

    def cog_unload(self):
        self.check_scheduled_standups.cancel()

    def init_db_tables(self):
        """Initialize the required database tables, using schedule_time for compatibility."""
        try:
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            CREATE TABLE IF NOT EXISTS standup_responses (
                                id SERIAL PRIMARY KEY,
                                user_id BIGINT NOT NULL,
                                guild_id BIGINT NOT NULL,
                                yesterday TEXT,
                                today TEXT,
                                blockers TEXT,
                                response_date DATE NOT NULL,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            );
                        """)
                        cur.execute("""
                            CREATE TABLE IF NOT EXISTS standup_schedules (
                                id SERIAL PRIMARY KEY,
                                guild_id BIGINT NOT NULL,
                                channel_id BIGINT NOT NULL,
                                schedule_time TIME NOT NULL,
                                days_of_week TEXT NOT NULL,
                                timezone TEXT DEFAULT 'UTC',
                                is_active BOOLEAN DEFAULT TRUE,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                UNIQUE(guild_id, channel_id)
                            );
                        """)
                        cur.execute("""
                            CREATE TABLE IF NOT EXISTS pair_sessions (
                                id SERIAL PRIMARY KEY,
                                guild_id BIGINT NOT NULL,
                                user1_id BIGINT NOT NULL,
                                user2_id BIGINT NOT NULL,
                                channel_id BIGINT,
                                start_time TIMESTAMP NOT NULL,
                                end_time TIMESTAMP,
                                topic TEXT,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            );
                        """)
                        conn.commit()
            logger.info("✅ Standup/Collaboration tables initialized")
        except Exception as e:
            logger.error(f"❌ Standup DB init failed: {e}")

    async def load_standup_schedules(self):
        """Load active standup schedules from db after the bot is ready."""
        try:
            await self.bot.wait_until_ready()
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            SELECT id, guild_id, channel_id, schedule_time, days_of_week, timezone
                            FROM standup_schedules WHERE is_active = TRUE
                        """)
                        self.standup_schedules = cur.fetchall()
            logger.info(f"✅ Loaded {len(self.standup_schedules)} standup schedules")
        except Exception as e:
            logger.error(f"❌ Failed to load standup schedules: {e}")

    # --- Standup commands ---

    @app_commands.command(name="standup", description="Submit your daily standup update")
    @app_commands.describe(
        yesterday="What did you work on yesterday?",
        today="What are you working on today?",
        blockers="Any blockers or issues? (optional)"
    )
    async def standup(
        self, 
        interaction: discord.Interaction, 
        yesterday: str, 
        today: str, 
        blockers: Optional[str] = "None"
    ):
        today_date = datetime.utcnow().date()
        try:
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            SELECT id FROM standup_responses
                            WHERE user_id = %s AND guild_id = %s AND response_date = %s
                        """, (interaction.user.id, interaction.guild_id, today_date))
                        existing = cur.fetchone()
                        if existing:
                            cur.execute("""
                                UPDATE standup_responses
                                SET yesterday = %s, today = %s, blockers = %s
                                WHERE id = %s
                            """, (yesterday, today, blockers, existing[0]))
                            action = "updated"
                        else:
                            cur.execute("""
                                INSERT INTO standup_responses 
                                (user_id, guild_id, yesterday, today, blockers, response_date)
                                VALUES (%s, %s, %s, %s, %s, %s)
                            """, (interaction.user.id, interaction.guild_id, yesterday, today, blockers, today_date))
                            action = "submitted"
                        conn.commit()
            embed = discord.Embed(
                title="✅ Standup Update Submitted",
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Yesterday", value=yesterday, inline=False)
            embed.add_field(name="Today", value=today, inline=False)
            embed.add_field(name="Blockers", value=blockers, inline=False)
            embed.set_footer(text=f"Standup {action} successfully")
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Standup submission error: {e}")
            await interaction.response.send_message("❌ Failed to submit standup update.", ephemeral=True)

    @app_commands.command(name="standup_summary", description="View today's standup summary")
    async def standup_summary(self, interaction: discord.Interaction):
        await interaction.response.defer()
        today_date = datetime.utcnow().date()
        try:
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            SELECT user_id, yesterday, today, blockers
                            FROM standup_responses
                            WHERE guild_id = %s AND response_date = %s
                            ORDER BY created_at
                        """, (interaction.guild_id, today_date))
                        responses = cur.fetchall()
            if not responses:
                await interaction.followup.send("📋 No standup updates submitted today yet.")
                return
            embed = discord.Embed(
                title=f"📊 Daily Standup Summary - {today_date}",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )
            for user_id, yesterday, today, blockers in responses:
                member = interaction.guild.get_member(user_id)
                name = member.display_name if member else f"User {user_id}"
                value = f"**Yesterday:** {yesterday}\n**Today:** {today}\n**Blockers:** {blockers}"
                embed.add_field(name=f"👤 {name}", value=value, inline=False)
            embed.set_footer(text=f"{len(responses)} team member(s) submitted updates")
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Standup summary error: {e}")
            await interaction.followup.send("❌ Failed to fetch standup summary.")

    @app_commands.command(name="standup_schedule", description="Schedule automatic standup reminders")
    @app_commands.describe(
        channel="Channel for standup messages",
        time="Time for standup (HH:MM 24-hour format)",
        days="Days of
