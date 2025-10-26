import discord
from discord import app_commands
from discord.ext import commands, tasks
import logging
from datetime import datetime, timedelta, time
import asyncio
from typing import Optional, Literal

logger = logging.getLogger(__name__)

class Standup(commands.Cog):
    """Daily standup, collaboration, and team pairing commands"""
    
    def __init__(self, bot, get_db_connection_func):
        self.bot = bot
        self.get_db_connection = get_db_connection_func
        self.init_db_tables()
        self.check_scheduled_standups.start()
        self.standup_schedules = []
        asyncio.create_task(self.load_standup_schedules())
    
    def cog_unload(self):
        """Clean up tasks when cog is unloaded"""
        self.check_scheduled_standups.cancel()
    
    def init_db_tables(self):
        """Initialize database tables for standup functionality"""
        try:
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        # Standup responses table
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
                        
                        # Standup schedules table
                        cur.execute("""
                            CREATE TABLE IF NOT EXISTS standup_schedules (
                                id SERIAL PRIMARY KEY,
                                guild_id BIGINT NOT NULL,
                                channel_id BIGINT NOT NULL,
                                time TIME NOT NULL,
                                days_of_week TEXT NOT NULL,
                                timezone TEXT DEFAULT 'UTC',
                                is_active BOOLEAN DEFAULT TRUE,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                UNIQUE(guild_id, channel_id)
                            );
                        """)
                        
                        # Pair programming sessions table
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
        """Load active standup schedules from database"""
        try:
            await self.bot.wait_until_ready()
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            SELECT id, guild_id, channel_id, time, days_of_week, timezone
                            FROM standup_schedules WHERE is_active = TRUE
                        """)
                        self.standup_schedules = cur.fetchall()
            logger.info(f"✅ Loaded {len(self.standup_schedules)} standup schedules")
        except Exception as e:
            logger.error(f"❌ Failed to load standup schedules: {e}")
    
    # ========== STANDUP COMMANDS ==========
    
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
        """Submit a daily standup update"""
        try:
            today_date = datetime.utcnow().date()
            
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        # Check if user already submitted today
                        cur.execute("""
                            SELECT id FROM standup_responses
                            WHERE user_id = %s AND guild_id = %s AND response_date = %s
                        """, (interaction.user.id, interaction.guild_id, today_date))
                        
                        existing = cur.fetchone()
                        
                        if existing:
                            # Update existing response
                            cur.execute("""
                                UPDATE standup_responses
                                SET yesterday = %s, today = %s, blockers = %s
                                WHERE id = %s
                            """, (yesterday, today, blockers, existing[0]))
                            action = "updated"
                        else:
                            # Insert new response
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
            await interaction.response.send_message(
                "❌ Failed to submit standup update.", 
                ephemeral=True
            )
    
    @app_commands.command(name="standup_summary", description="View today's standup summary")
    async def standup_summary(self, interaction: discord.Interaction):
        """Display a summary of today's standup responses"""
        try:
            await interaction.response.defer()
            
            today_date = datetime.utcnow().date()
            
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
                if member:
                    value = f"**Yesterday:** {yesterday}\n**Today:** {today}\n**Blockers:** {blockers}"
                    embed.add_field(
                        name=f"👤 {member.display_name}",
                        value=value,
                        inline=False
                    )
            
            embed.set_footer(text=f"{len(responses)} team member(s) submitted updates")
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Standup summary error: {e}")
            await interaction.followup.send("❌ Failed to fetch standup summary.")
    
    @app_commands.command(name="standup_schedule", description="Schedule automatic standup reminders")
    @app_commands.describe(
        channel="Channel for standup messages",
        time="Time for standup (HH:MM format, 24-hour)",
        days="Days of the week (comma-separated: Mon,Tue,Wed,Thu,Fri)"
    )
    async def standup_schedule(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        time: str,
        days: str = "Mon,Tue,Wed,Thu,Fri"
    ):
        """Schedule automatic standup reminders"""
        try:
            # Validate time format
            try:
                hour, minute = map(int, time.split(':'))
                if not (0 <= hour < 24 and 0 <= minute < 60):
                    raise ValueError
            except:
                await interaction.response.send_message(
                    "❌ Invalid time format. Use HH:MM (24-hour format).",
                    ephemeral=True
                )
                return
            
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO standup_schedules 
                            (guild_id, channel_id, time, days_of_week)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (guild_id, channel_id) 
                            DO UPDATE SET time = EXCLUDED.time, 
                                        days_of_week = EXCLUDED.days_of_week,
                                        is_active = TRUE
                        """, (interaction.guild_id, channel.id, time, days))
                        conn.commit()
            
            await self.load_standup_schedules()
            
            embed = discord.Embed(
                title="⏰ Standup Schedule Set",
                color=discord.Color.green()
            )
            embed.add_field(name="Channel", value=channel.mention, inline=False)
            embed.add_field(name="Time", value=time, inline=True)
            embed.add_field(name="Days", value=days, inline=True)
            embed.set_footer(text="Standup reminders will be posted automatically")
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"Standup schedule error: {e}")
            await interaction.response.send_message(
                "❌ Failed to schedule standup.",
                ephemeral=True
            )
    
    @app_commands.command(name="standup_cancel", description="Cancel scheduled standup reminders")
    async def standup_cancel(self, interaction: discord.Interaction):
        """Cancel automatic standup reminders for this server"""
        try:
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            UPDATE standup_schedules
                            SET is_active = FALSE
                            WHERE guild_id = %s
                        """, (interaction.guild_id,))
                        conn.commit()
            
            await self.load_standup_schedules()
            await interaction.response.send_message("✅ Standup schedules have been cancelled.")
            
        except Exception as e:
            logger.error(f"Standup cancel error: {e}")
            await interaction.response.send_message(
                "❌ Failed to cancel standup schedule.",
                ephemeral=True
            )
    
    # ========== PAIR PROGRAMMING COMMANDS ==========
    
    @app_commands.command(name="pair_random", description="Get paired with a random online member")
    async def pair_random(self, interaction: discord.Interaction):
        """Randomly pair with another online member for collaboration"""
        try:
            # Get online members excluding bots and the requester
            online_members = [
                m for m in interaction.guild.members
                if m.status != discord.Status.offline 
                and not m.bot 
                and m.id != interaction.user.id
            ]
            
            if not online_members:
                await interaction.response.send_message(
                    "❌ No other members are currently online.",
                    ephemeral=True
                )
                return
            
            import random
            partner = random.choice(online_members)
            
            embed = discord.Embed(
                title="👥 Pair Programming Match",
                description=f"{interaction.user.mention} has been paired with {partner.mention}!",
                color=discord.Color.purple(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(
                name="Next Steps",
                value="• Start a voice channel\n• Share your screen\n• Start coding together!",
                inline=False
            )
            
            # Log the pairing
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO pair_sessions 
                            (guild_id, user1_id, user2_id, start_time)
                            VALUES (%s, %s, %s, %s)
                        """, (interaction.guild_id, interaction.user.id, partner.id, datetime.utcnow()))
                        conn.commit()
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"Pair random error: {e}")
            await interaction.response.send_message(
                "❌ Failed to find a pair.",
                ephemeral=True
            )
    
    @app_commands.command(name="pair_with", description="Request to pair with a specific member")
    @app_commands.describe(member="The member you want to pair with")
    async def pair_with(self, interaction: discord.Interaction, member: discord.Member):
        """Request to pair with a specific member"""
        try:
            if member.bot:
                await interaction.response.send_message(
                    "❌ You cannot pair with a bot.",
                    ephemeral=True
                )
                return
            
            if member.id == interaction.user.id:
                await interaction.response.send_message(
                    "❌ You cannot pair with yourself.",
                    ephemeral=True
                )
                return
            
            embed = discord.Embed(
                title="👥 Pair Programming Request",
                description=f"{interaction.user.mention} wants to pair program with you!",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(
                name="Respond",
                value="React with ✅ to accept or ❌ to decline",
                inline=False
            )
            
            await interaction.response.send_message(
                content=member.mention,
                embed=embed
            )
            
            message = await interaction.original_response()
            await message.add_reaction("✅")
            await message.add_reaction("❌")
            
        except Exception as e:
            logger.error(f"Pair with error: {e}")
            await interaction.response.send_message(
                "❌ Failed to send pair request.",
                ephemeral=True
            )
    
    @app_commands.command(name="pair_stats", description="View your pair programming statistics")
    @app_commands.describe(member="Member to check stats for (optional)")
    async def pair_stats(self, interaction: discord.Interaction, member: Optional[discord.Member] = None):
        """View pair programming statistics"""
        try:
            target = member or interaction.user
            
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            SELECT COUNT(*) FROM pair_sessions
                            WHERE guild_id = %s AND (user1_id = %s OR user2_id = %s)
                        """, (interaction.guild_id, target.id, target.id))
                        
                        total_sessions = cur.fetchone()[0]
            
            embed = discord.Embed(
                title=f"📊 Pair Programming Stats: {target.display_name}",
                color=discord.Color.gold()
            )
            embed.add_field(name="Total Sessions", value=str(total_sessions), inline=True)
            embed.set_thumbnail(url=target.display_avatar.url)
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"Pair stats error: {e}")
            await interaction.response.send_message(
                "❌ Failed to fetch pair stats.",
                ephemeral=True
            )
    
    # ========== BACKGROUND TASK ==========
    
    @tasks.loop(minutes=1)
    async def check_scheduled_standups(self):
        """Check if it's time to post standup reminders"""
        try:
            now = datetime.utcnow()
            current_time = now.strftime("%H:%M")
            current_day = now.strftime("%a")
            
            for schedule in self.standup_schedules:
                schedule_id, guild_id, channel_id, sched_time, days_of_week, timezone = schedule
                
                # Check if current day is in the schedule
                if current_day not in days_of_week:
                    continue
                
                # Check if current time matches (within the minute)
                if current_time == sched_time:
                    guild = self.bot.get_guild(guild_id)
                    if guild:
                        channel = guild.get_channel(channel_id)
                        if channel:
                            await self.post_standup_reminder(channel, guild_id)
        
        except Exception as e:
            logger.error(f"Check scheduled standups error: {e}")
    
    @check_scheduled_standups.before_loop
    async def before_check_scheduled_standups(self):
        """Wait until the bot is ready before starting the task"""
        await self.bot.wait_until_ready()
    
    async def post_standup_reminder(self, channel: discord.TextChannel, guild_id: int):
        """Post a standup reminder to the specified channel"""
        try:
            embed = discord.Embed(
                title="🌅 Daily Standup Time!",
                description="Time to submit your daily standup update using `/standup`",
                color=discord.Color.orange(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(
                name="What to include:",
                value="• What you did yesterday\n• What you're doing today\n• Any blockers",
                inline=False
            )
            
            await channel.send(embed=embed)
            logger.info(f"Posted standup reminder to guild {guild_id}")
            
        except Exception as e:
            logger.error(f"Post standup reminder error: {e}")


async def setup(bot: commands.Bot):
    """Setup function to load the cog"""
    get_db_connection_func = getattr(bot, "get_db_connection", None)
    if not get_db_connection_func:
        logger.error("❌ get_db_connection not found on bot instance")
        raise Exception("Database connection function not found")
    
    await bot.add_cog(Standup(bot, get_db_connection_func))
    logger.info("✅ Standup/Collaboration cog loaded successfully")
