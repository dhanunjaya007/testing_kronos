import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta
import logging
from typing import Optional, Literal
import asyncio

logger = logging.getLogger(__name__)

class Productivity(commands.Cog):
    def __init__(self, bot, get_db_connection_func):
        self.bot = bot
        self.get_db_connection = get_db_connection_func
        self.focus_sessions = {}
        self.pomodoro_sessions = {}
        self.dnd_users = {}
        self.init_db_tables()

    def init_db_tables(self):
        """Initialize productivity tables"""
        try:
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        # Focus sessions table
                        cur.execute("""
                            CREATE TABLE IF NOT EXISTS focus_sessions (
                                id SERIAL PRIMARY KEY,
                                session_id TEXT NOT NULL UNIQUE,
                                user_id BIGINT NOT NULL,
                                guild_id BIGINT NOT NULL,
                                channel_id BIGINT NOT NULL,
                                start_time TIMESTAMP NOT NULL,
                                end_time TIMESTAMP,
                                duration_minutes INT,
                                focus_type TEXT DEFAULT 'focus',
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                        """)
                        
                        # Pomodoro sessions table
                        cur.execute("""
                            CREATE TABLE IF NOT EXISTS pomodoro_sessions (
                                id SERIAL PRIMARY KEY,
                                session_id TEXT NOT NULL UNIQUE,
                                user_id BIGINT NOT NULL,
                                guild_id BIGINT NOT NULL,
                                channel_id BIGINT NOT NULL,
                                start_time TIMESTAMP NOT NULL,
                                end_time TIMESTAMP,
                                duration_minutes INT DEFAULT 25,
                                break_duration INT DEFAULT 5,
                                completed_pomodoros INT DEFAULT 0,
                                is_break BOOLEAN DEFAULT FALSE,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                        """)
                        
                        # DND status table
                        cur.execute("""
                            CREATE TABLE IF NOT EXISTS dnd_status (
                                id SERIAL PRIMARY KEY,
                                user_id BIGINT NOT NULL,
                                guild_id BIGINT NOT NULL,
                                start_time TIMESTAMP NOT NULL,
                                end_time TIMESTAMP,
                                duration_minutes INT,
                                reason TEXT,
                                active BOOLEAN DEFAULT TRUE,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                        """)
                        
                        # Productivity stats table
                        cur.execute("""
                            CREATE TABLE IF NOT EXISTS productivity_stats (
                                id SERIAL PRIMARY KEY,
                                user_id BIGINT NOT NULL,
                                guild_id BIGINT NOT NULL,
                                total_focus_minutes INT DEFAULT 0,
                                total_pomodoros INT DEFAULT 0,
                                total_dnd_minutes INT DEFAULT 0,
                                focus_sessions_count INT DEFAULT 0,
                                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                UNIQUE(user_id, guild_id)
                            )
                        """)
                        
                        conn.commit()
                    logger.info("✅ Productivity tables initialized")
                else:
                    logger.warning("⚠️ Database connection not available - tables not initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize productivity tables: {e}")
            import traceback
            traceback.print_exc()

    # ===== FOCUS COMMANDS =====

    @commands.hybrid_group(name="focus", description="Manage focus sessions", invoke_without_command=True)
    async def focus(self, ctx: commands.Context):
        """Focus commands help"""
        embed = discord.Embed(
            title="🎯 Focus Commands",
            description=(
                "**/focus start <duration>** - Start focus session\n"
                "**/focus end** - End focus session\n"
                "**/focus stats [user]** - View focus statistics\n"
                "**/focus list** - List active focus sessions"
            ),
            color=discord.Color.purple()
        )
        await ctx.send(embed=embed)

    @focus.command(name="start", description="Start a focus session")
    @app_commands.describe(
        duration="Focus duration in minutes (default: 60)",
        type="Type of focus session"
    )
    async def focus_start(self, ctx: commands.Context, duration: int = 60, 
                         type: Literal["focus", "deep_work", "study", "coding", "writing"] = "focus"):
        """Start focus session"""
        try:
            if ctx.author.id in self.focus_sessions:
                await ctx.send("❌ You already have an active focus session! Use `/focus end` to stop it first.", ephemeral=True)
                return
            
            if duration < 5 or duration > 480:  # 5 minutes to 8 hours
                await ctx.send("❌ Focus duration must be between 5 and 480 minutes.", ephemeral=True)
                return
            
            session_id = f"FOCUS{int(datetime.utcnow().timestamp())}"
            start_time = datetime.utcnow()
            
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO focus_sessions (session_id, user_id, guild_id, channel_id, start_time, focus_type)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (session_id, ctx.author.id, ctx.guild.id, ctx.channel.id, start_time, type))
                        conn.commit()
                    
                    # Store in memory
                    self.focus_sessions[ctx.author.id] = {
                        'session_id': session_id,
                        'start_time': start_time,
                        'duration': duration,
                        'type': type,
                        'channel_id': ctx.channel.id
                    }
                    
                    embed = discord.Embed(
                        title="🎯 Focus Session Started",
                        description=f"**Duration:** {duration} minutes\n**Type:** {type.replace('_', ' ').title()}",
                        color=discord.Color.green()
                    )
                    embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
                    embed.set_footer(text=f"Session ID: {session_id}")
                    
                    message = await ctx.send(embed=embed)
                    
                    # Set up auto-end after duration
                    await asyncio.sleep(duration * 60)  # Convert to seconds
                    
                    if ctx.author.id in self.focus_sessions:
                        await self._end_focus_session(ctx.author.id, ctx.channel)
                else:
                    await ctx.send("❌ Database connection unavailable. Please try again later.", ephemeral=True)
                    
        except Exception as e:
            logger.error(f"focus_start error: {e}")
            await ctx.send("❌ Failed to start focus session.", ephemeral=True)

    @focus.command(name="end", description="End current focus session")
    async def focus_end(self, ctx: commands.Context):
        """End focus session"""
        try:
            if ctx.author.id not in self.focus_sessions:
                await ctx.send("❌ No active focus session found!", ephemeral=True)
                return
            
            await self._end_focus_session(ctx.author.id, ctx.channel)
            
        except Exception as e:
            logger.error(f"focus_end error: {e}")
            await ctx.send("❌ Failed to end focus session.", ephemeral=True)

    async def _end_focus_session(self, user_id, channel):
        """Helper method to end focus session"""
        try:
            session_data = self.focus_sessions.get(user_id)
            if not session_data:
                return
            
            session_id = session_data['session_id']
            start_time = session_data['start_time']
            duration = session_data['duration']
            focus_type = session_data['type']
            
            end_time = datetime.utcnow()
            actual_duration = int((end_time - start_time).total_seconds() / 60)
            
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            UPDATE focus_sessions 
                            SET end_time = %s, duration_minutes = %s
                            WHERE session_id = %s
                        """, (end_time, actual_duration, session_id))
                        
                        # Update productivity stats
                        cur.execute("""
                            INSERT INTO productivity_stats (user_id, guild_id, total_focus_minutes, focus_sessions_count)
                            VALUES (%s, %s, %s, 1)
                            ON CONFLICT (user_id, guild_id) 
                            DO UPDATE SET 
                                total_focus_minutes = productivity_stats.total_focus_minutes + %s,
                                focus_sessions_count = productivity_stats.focus_sessions_count + 1,
                                last_updated = CURRENT_TIMESTAMP
                        """, (user_id, channel.guild.id, actual_duration, actual_duration))
                        
                        conn.commit()
                    
                    # Remove from memory
                    del self.focus_sessions[user_id]
                    
                    user = self.bot.get_user(user_id)
                    embed = discord.Embed(
                        title="✅ Focus Session Completed",
                        description=f"**Duration:** {actual_duration} minutes\n**Type:** {focus_type.replace('_', ' ').title()}",
                        color=discord.Color.orange()
                    )
                    embed.set_author(name=user.display_name if user else "Unknown", icon_url=user.avatar.url if user and user.avatar else None)
                    embed.set_footer(text=f"Session ID: {session_id}")
                    
                    await channel.send(embed=embed)
        except Exception as e:
            logger.error(f"_end_focus_session error: {e}")

    @focus.command(name="stats", description="View focus statistics")
    @app_commands.describe(user="User to check stats for (optional)")
    async def focus_stats(self, ctx: commands.Context, user: discord.Member = None):
        """View focus statistics"""
        try:
            target_user = user or ctx.author
            
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        # Get productivity stats
                        cur.execute("""
                            SELECT total_focus_minutes, focus_sessions_count, total_pomodoros
                            FROM productivity_stats 
                            WHERE user_id = %s AND guild_id = %s
                        """, (target_user.id, ctx.guild.id))
                        stats = cur.fetchone()
                        
                        if not stats:
                            await ctx.send(f"📊 No focus data found for {target_user.display_name}.", ephemeral=True)
                            return
                        
                        total_focus_minutes, focus_sessions_count, total_pomodoros = stats
                        
                        # Get recent focus sessions (last 30 days)
                        cur.execute("""
                            SELECT COUNT(*), AVG(duration_minutes), focus_type
                            FROM focus_sessions 
                            WHERE user_id = %s AND guild_id = %s 
                            AND start_time >= %s
                            GROUP BY focus_type
                        """, (target_user.id, ctx.guild.id, datetime.utcnow() - timedelta(days=30)))
                        recent_sessions = cur.fetchall()
                        
                        embed = discord.Embed(
                            title=f"📊 Focus Stats - {target_user.display_name}",
                            color=discord.Color.purple()
                        )
                        
                        embed.add_field(
                            name="🎯 Total Focus Time",
                            value=f"{total_focus_minutes} minutes ({total_focus_minutes // 60}h {total_focus_minutes % 60}m)",
                            inline=True
                        )
                        embed.add_field(
                            name="📈 Total Sessions",
                            value=str(focus_sessions_count),
                            inline=True
                        )
                        embed.add_field(
                            name="🍅 Pomodoros",
                            value=str(total_pomodoros),
                            inline=True
                        )
                        
                        if recent_sessions:
                            recent_text = ""
                            for count, avg_duration, focus_type in recent_sessions:
                                recent_text += f"**{focus_type.replace('_', ' ').title()}:** {count} sessions (avg: {avg_duration:.1f}min)\n"
                            embed.add_field(
                                name="📅 Recent Activity (30 days)",
                                value=recent_text,
                                inline=False
                            )
                        
                        embed.set_thumbnail(url=target_user.avatar.url if target_user.avatar else target_user.default_avatar.url)
                        await ctx.send(embed=embed)
                else:
                    await ctx.send("❌ Database connection unavailable. Please try again later.", ephemeral=True)
                    
        except Exception as e:
            logger.error(f"focus_stats error: {e}")
            await ctx.send("❌ Failed to get focus stats.", ephemeral=True)

    # ===== POMODORO COMMANDS =====

    @commands.hybrid_group(name="pomodoro", description="Manage Pomodoro sessions", invoke_without_command=True)
    async def pomodoro(self, ctx: commands.Context):
        """Pomodoro commands help"""
        embed = discord.Embed(
            title="🍅 Pomodoro Commands",
            description=(
                "**/pomodoro start [duration]** - Start Pomodoro timer (25min default)\n"
                "**/pomodoro break** - Start break timer\n"
                "**/pomodoro end** - End current session\n"
                "**/pomodoro stats** - View Pomodoro statistics"
            ),
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)

    @pomodoro.command(name="start", description="Start Pomodoro timer")
    @app_commands.describe(duration="Pomodoro duration in minutes (default: 25)")
    async def pomodoro_start(self, ctx: commands.Context, duration: int = 25):
        """Start Pomodoro session"""
        try:
            if ctx.author.id in self.pomodoro_sessions:
                await ctx.send("❌ You already have an active Pomodoro session! Use `/pomodoro end` to stop it first.", ephemeral=True)
                return
            
            if duration < 5 or duration > 60:
                await ctx.send("❌ Pomodoro duration must be between 5 and 60 minutes.", ephemeral=True)
                return
            
            session_id = f"POMO{int(datetime.utcnow().timestamp())}"
            start_time = datetime.utcnow()
            
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO pomodoro_sessions (session_id, user_id, guild_id, channel_id, start_time, duration_minutes)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (session_id, ctx.author.id, ctx.guild.id, ctx.channel.id, start_time, duration))
                        conn.commit()
                    
                    # Store in memory
                    self.pomodoro_sessions[ctx.author.id] = {
                        'session_id': session_id,
                        'start_time': start_time,
                        'duration': duration,
                        'completed_pomodoros': 0,
                        'is_break': False,
                        'channel_id': ctx.channel.id
                    }
                    
                    embed = discord.Embed(
                        title="🍅 Pomodoro Started",
                        description=f"**Duration:** {duration} minutes\n**Focus time!** 🎯",
                        color=discord.Color.red()
                    )
                    embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
                    embed.set_footer(text=f"Session ID: {session_id}")
                    
                    message = await ctx.send(embed=embed)
                    
                    # Set up auto-end after duration
                    await asyncio.sleep(duration * 60)
                    
                    if ctx.author.id in self.pomodoro_sessions:
                        await self._complete_pomodoro(ctx.author.id, ctx.channel)
                else:
                    await ctx.send("❌ Database connection unavailable. Please try again later.", ephemeral=True)
                    
        except Exception as e:
            logger.error(f"pomodoro_start error: {e}")
            await ctx.send("❌ Failed to start Pomodoro session.", ephemeral=True)

    @pomodoro.command(name="break", description="Start break timer")
    @app_commands.describe(duration="Break duration in minutes (default: 5)")
    async def pomodoro_break(self, ctx: commands.Context, duration: int = 5):
        """Start break timer"""
        try:
            if ctx.author.id not in self.pomodoro_sessions:
                await ctx.send("❌ No active Pomodoro session found! Start one with `/pomodoro start`.", ephemeral=True)
                return
            
            session_data = self.pomodoro_sessions[ctx.author.id]
            session_data['is_break'] = True
            session_data['break_duration'] = duration
            
            embed = discord.Embed(
                title="☕ Break Time!",
                description=f"**Duration:** {duration} minutes\n**Take a well-deserved break!** ☕",
                color=discord.Color.blue()
            )
            embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
            
            await ctx.send(embed=embed)
            
            # Set up auto-end after break duration
            await asyncio.sleep(duration * 60)
            
            if ctx.author.id in self.pomodoro_sessions and self.pomodoro_sessions[ctx.author.id]['is_break']:
                embed = discord.Embed(
                    title="🎯 Break Over!",
                    description="**Ready for another Pomodoro?** Use `/pomodoro start` to continue!",
                    color=discord.Color.green()
                )
                await ctx.channel.send(embed=embed)
                
        except Exception as e:
            logger.error(f"pomodoro_break error: {e}")
            await ctx.send("❌ Failed to start break.", ephemeral=True)

    async def _complete_pomodoro(self, user_id, channel):
        """Helper method to complete Pomodoro"""
        try:
            session_data = self.pomodoro_sessions.get(user_id)
            if not session_data:
                return
            
            session_id = session_data['session_id']
            completed_pomodoros = session_data['completed_pomodoros'] + 1
            
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            UPDATE pomodoro_sessions 
                            SET completed_pomodoros = %s, is_break = TRUE
                            WHERE session_id = %s
                        """, (completed_pomodoros, session_id))
                        
                        # Update productivity stats
                        cur.execute("""
                            INSERT INTO productivity_stats (user_id, guild_id, total_pomodoros)
                            VALUES (%s, %s, 1)
                            ON CONFLICT (user_id, guild_id) 
                            DO UPDATE SET 
                                total_pomodoros = productivity_stats.total_pomodoros + 1,
                                last_updated = CURRENT_TIMESTAMP
                        """, (user_id, channel.guild.id))
                        
                        conn.commit()
                    
                    # Update in memory
                    self.pomodoro_sessions[user_id]['completed_pomodoros'] = completed_pomodoros
                    self.pomodoro_sessions[user_id]['is_break'] = True
                    
                    user = self.bot.get_user(user_id)
                    embed = discord.Embed(
                        title="🍅 Pomodoro Complete!",
                        description=f"**Completed Pomodoros:** {completed_pomodoros}\n**Time for a break!** ☕",
                        color=discord.Color.orange()
                    )
                    embed.set_author(name=user.display_name if user else "Unknown", icon_url=user.avatar.url if user and user.avatar else None)
                    
                    await channel.send(embed=embed)
        except Exception as e:
            logger.error(f"_complete_pomodoro error: {e}")

    # ===== DND COMMANDS =====

    @commands.hybrid_group(name="dnd", description="Do Not Disturb mode", invoke_without_command=True)
    async def dnd(self, ctx: commands.Context):
        """DND commands help"""
        embed = discord.Embed(
            title="🔕 Do Not Disturb Commands",
            description=(
                "**/dnd start <duration> [reason]** - Enable DND mode\n"
                "**/dnd end** - Disable DND mode\n"
                "**/dnd status** - Check your DND status"
            ),
            color=discord.Color.dark_gray()
        )
        await ctx.send(embed=embed)

    @dnd.command(name="start", description="Enable Do Not Disturb mode")
    @app_commands.describe(
        duration="DND duration in minutes",
        reason="Reason for DND mode"
    )
    async def dnd_start(self, ctx: commands.Context, duration: int, *, reason: str = "Focus time"):
        """Set DND mode"""
        try:
            if ctx.author.id in self.dnd_users:
                await ctx.send("❌ You're already in DND mode! Use `/dnd end` to disable it first.", ephemeral=True)
                return
            
            if duration < 5 or duration > 480:  # 5 minutes to 8 hours
                await ctx.send("❌ DND duration must be between 5 and 480 minutes.", ephemeral=True)
                return
            
            start_time = datetime.utcnow()
            end_time = start_time + timedelta(minutes=duration)
            
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO dnd_status (user_id, guild_id, start_time, end_time, duration_minutes, reason)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (ctx.author.id, ctx.guild.id, start_time, end_time, duration, reason))
                        conn.commit()
                    
                    # Store in memory
                    self.dnd_users[ctx.author.id] = {
                        'start_time': start_time,
                        'end_time': end_time,
                        'duration': duration,
                        'reason': reason,
                        'guild_id': ctx.guild.id
                    }
                    
                    embed = discord.Embed(
                        title="🔕 Do Not Disturb Mode",
                        description=f"**Duration:** {duration} minutes\n**Reason:** {reason}",
                        color=discord.Color.dark_gray()
                    )
                    embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
                    embed.set_footer(text=f"Ends at {end_time.strftime('%H:%M')}")
                    
                    await ctx.send(embed=embed)
                    
                    # Set up auto-end after duration
                    await asyncio.sleep(duration * 60)
                    
                    if ctx.author.id in self.dnd_users:
                        await self._end_dnd(ctx.author.id, ctx.channel)
                else:
                    await ctx.send("❌ Database connection unavailable. Please try again later.", ephemeral=True)
                    
        except Exception as e:
            logger.error(f"dnd_start error: {e}")
            await ctx.send("❌ Failed to set DND mode.", ephemeral=True)

    @dnd.command(name="end", description="Disable Do Not Disturb mode")
    async def dnd_end(self, ctx: commands.Context):
        """End DND mode"""
        try:
            if ctx.author.id not in self.dnd_users:
                await ctx.send("❌ You're not in DND mode!", ephemeral=True)
                return
            
            await self._end_dnd(ctx.author.id, ctx.channel)
            
        except Exception as e:
            logger.error(f"dnd_end error: {e}")
            await ctx.send("❌ Failed to end DND mode.", ephemeral=True)

    async def _end_dnd(self, user_id, channel):
        """Helper method to end DND"""
        try:
            dnd_data = self.dnd_users.get(user_id)
            if not dnd_data:
                return
            
            duration = dnd_data['duration']
            
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            UPDATE dnd_status 
                            SET active = FALSE, end_time = %s
                            WHERE user_id = %s AND guild_id = %s AND active = TRUE
                        """, (datetime.utcnow(), user_id, dnd_data['guild_id']))
                        
                        # Update productivity stats
                        cur.execute("""
                            INSERT INTO productivity_stats (user_id, guild_id, total_dnd_minutes)
                            VALUES (%s, %s, %s)
                            ON CONFLICT (user_id, guild_id) 
                            DO UPDATE SET 
                                total_dnd_minutes = productivity_stats.total_dnd_minutes + %s,
                                last_updated = CURRENT_TIMESTAMP
                        """, (user_id, dnd_data['guild_id'], duration, duration))
                        
                        conn.commit()
                    
                    # Remove from memory
                    del self.dnd_users[user_id]
                    
                    user = self.bot.get_user(user_id)
                    embed = discord.Embed(
                        title="🔔 DND Mode Ended",
                        description=f"**Duration:** {duration} minutes\n**Welcome back!** 👋",
                        color=discord.Color.green()
                    )
                    embed.set_author(name=user.display_name if user else "Unknown", icon_url=user.avatar.url if user and user.avatar else None)
                    
                    await channel.send(embed=embed)
        except Exception as e:
            logger.error(f"_end_dnd error: {e}")

async def setup(bot: commands.Bot):
    """Setup function for the cog"""
    try:
        get_db_connection_func = getattr(bot, "get_db_connection", None)
        if not get_db_connection_func:
            logger.error("❌ get_db_connection not found on bot instance")
            return
        
        await bot.add_cog(Productivity(bot, get_db_connection_func))
        logger.info("✅ Productivity cog loaded successfully")
    except Exception as e:
        logger.error(f"❌ Failed to setup Productivity cog: {e}")
        import traceback
        traceback.print_exc()
