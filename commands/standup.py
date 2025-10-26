import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta, time
import logging
from typing import Optional, Literal
import asyncio

logger = logging.getLogger(__name__)

class Standup(commands.Cog):
    def __init__(self, bot, get_db_connection_func):
        self.bot = bot
        self.get_db_connection = get_db_connection_func
        self.standup_schedules = {}
        self.pair_sessions = {}
        self.sync_requests = {}
        self.init_db_tables()
        self.load_standup_schedules()

    def init_db_tables(self):
        """Initialize standup and collaboration tables"""
        try:
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        # Standup schedules table
                        cur.execute("""
                            CREATE TABLE IF NOT EXISTS standup_schedules (
                                id SERIAL PRIMARY KEY,
                                guild_id BIGINT NOT NULL,
                                channel_id BIGINT NOT NULL,
                                standup_time TIME NOT NULL,
                                timezone TEXT DEFAULT 'UTC',
                                template TEXT DEFAULT 'What did you do yesterday? What will you do today? Any blockers?',
                                active BOOLEAN DEFAULT TRUE,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                        """)
                        
                        # Standup posts table
                        cur.execute("""
                            CREATE TABLE IF NOT EXISTS standup_posts (
                                id SERIAL PRIMARY KEY,
                                user_id BIGINT NOT NULL,
                                guild_id BIGINT NOT NULL,
                                channel_id BIGINT NOT NULL,
                                post_date DATE NOT NULL,
                                content TEXT NOT NULL,
                                skipped BOOLEAN DEFAULT FALSE,
                                skip_reason TEXT,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                UNIQUE(user_id, guild_id, post_date)
                            )
                        """)
                        
                        # Pair programming sessions table
                        cur.execute("""
                            CREATE TABLE IF NOT EXISTS pair_sessions (
                                id SERIAL PRIMARY KEY,
                                session_id TEXT NOT NULL UNIQUE,
                                user1_id BIGINT NOT NULL,
                                user2_id BIGINT NOT NULL,
                                guild_id BIGINT NOT NULL,
                                channel_id BIGINT NOT NULL,
                                start_time TIMESTAMP NOT NULL,
                                end_time TIMESTAMP,
                                duration_minutes INT,
                                topic TEXT,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                        """)
                        
                        # Sync requests table
                        cur.execute("""
                            CREATE TABLE IF NOT EXISTS sync_requests (
                                id SERIAL PRIMARY KEY,
                                request_id TEXT NOT NULL UNIQUE,
                                requester_id BIGINT NOT NULL,
                                target_id BIGINT NOT NULL,
                                guild_id BIGINT NOT NULL,
                                channel_id BIGINT NOT NULL,
                                message TEXT,
                                status TEXT CHECK (status IN ('pending', 'accepted', 'declined', 'completed')) DEFAULT 'pending',
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                responded_at TIMESTAMP
                            )
                        """)
                        
                        conn.commit()
                    logger.info("✅ Standup/Collaboration tables initialized")
                else:
                    logger.warning("⚠️ Database connection not available - tables not initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize standup/collaboration tables: {e}")
            import traceback
            traceback.print_exc()

    def load_standup_schedules(self):
        """Load standup schedules from database"""
        try:
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            SELECT guild_id, channel_id, standup_time, timezone, template, active
                            FROM standup_schedules WHERE active = TRUE
                        """)
                        rows = cur.fetchall()
                        
                        for guild_id, channel_id, standup_time, timezone, template, active in rows:
                            self.standup_schedules[guild_id] = {
                                'channel_id': channel_id,
                                'time': standup_time,
                                'timezone': timezone,
                                'template': template,
                                'active': active
                            }
                        logger.info(f"✅ Loaded {len(rows)} standup schedules")
        except Exception as e:
            logger.error(f"❌ Failed to load standup schedules: {e}")

    # ===== STANDUP COMMANDS =====

    @commands.hybrid_group(name="standup", description="Manage team standups", invoke_without_command=True)
    async def standup(self, ctx: commands.Context):
        """Standup commands help"""
        embed = discord.Embed(
            title="📋 Standup Commands",
            description=(
                "**/standup schedule <time>** - Schedule daily standup time\n"
                "**/standup post** - Manually post your standup update\n"
                "**/standup skip** - Skip today's standup with reason\n"
                "**/standup template <format>** - Customize standup format\n"
                "**/standup list** - View standup history\n"
                "**/standup stats** - View standup statistics"
            ),
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)

    @standup.command(name="schedule", description="Schedule daily standup time")
    @app_commands.describe(
        time="Standup time (HH:MM format, 24-hour)",
        timezone="Timezone (default: UTC)",
        template="Custom standup template"
    )
    async def standup_schedule(self, ctx: commands.Context, time: str, 
                             timezone: str = "UTC", *, template: str = None):
        """Schedule daily standup"""
        try:
            # Parse time
            try:
                standup_time = datetime.strptime(time, "%H:%M").time()
            except ValueError:
                await ctx.send("❌ Invalid time format. Use HH:MM (24-hour)", ephemeral=True)
                return
            
            default_template = "What did you do yesterday? What will you do today? Any blockers?"
            template_text = template or default_template
            
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        # Check if schedule exists
                        cur.execute("""
                            SELECT id FROM standup_schedules 
                            WHERE guild_id = %s AND active = TRUE
                        """, (ctx.guild.id,))
                        
                        if cur.fetchone():
                            # Update existing
                            cur.execute("""
                                UPDATE standup_schedules 
                                SET channel_id = %s, standup_time = %s, timezone = %s, template = %s
                                WHERE guild_id = %s AND active = TRUE
                            """, (ctx.channel.id, standup_time, timezone, template_text, ctx.guild.id))
                        else:
                            # Create new
                            cur.execute("""
                                INSERT INTO standup_schedules (guild_id, channel_id, standup_time, timezone, template)
                                VALUES (%s, %s, %s, %s, %s)
                            """, (ctx.guild.id, ctx.channel.id, standup_time, timezone, template_text))
                        
                        conn.commit()
                    
                    # Update in-memory cache
                    self.standup_schedules[ctx.guild.id] = {
                        'channel_id': ctx.channel.id,
                        'time': standup_time,
                        'timezone': timezone,
                        'template': template_text,
                        'active': True
                    }
                    
                    embed = discord.Embed(
                        title="✅ Standup Scheduled",
                        description=f"Daily standup scheduled for **{time}** ({timezone})",
                        color=discord.Color.green()
                    )
                    embed.add_field(name="Channel", value=ctx.channel.mention, inline=True)
                    embed.add_field(name="Template", value=template_text, inline=False)
                    await ctx.send(embed=embed)
                else:
                    await ctx.send("❌ Database connection unavailable. Please try again later.", ephemeral=True)
                    
        except Exception as e:
            logger.error(f"standup_schedule error: {e}")
            await ctx.send("❌ Failed to schedule standup.", ephemeral=True)

    @standup.command(name="post", description="Manually post your standup update")
    @app_commands.describe(content="Your standup update")
    async def standup_post(self, ctx: commands.Context, *, content: str):
        """Post standup update"""
        try:
            today = datetime.utcnow().date()
            
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        # Check if already posted today
                        cur.execute("""
                            SELECT id FROM standup_posts 
                            WHERE user_id = %s AND guild_id = %s AND post_date = %s
                        """, (ctx.author.id, ctx.guild.id, today))
                        
                        if cur.fetchone():
                            await ctx.send("❌ You've already posted your standup today!", ephemeral=True)
                            return
                        
                        # Save standup post
                        cur.execute("""
                            INSERT INTO standup_posts (user_id, guild_id, channel_id, post_date, content)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (ctx.author.id, ctx.guild.id, ctx.channel.id, today, content))
                        conn.commit()
                    
                    embed = discord.Embed(
                        title="📋 Standup Update",
                        description=content,
                        color=discord.Color.blue()
                    )
                    embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
                    embed.set_footer(text=f"Posted on {today}")
                    
                    await ctx.send(embed=embed)
                else:
                    await ctx.send("❌ Database connection unavailable. Please try again later.", ephemeral=True)
                    
        except Exception as e:
            logger.error(f"standup_post error: {e}")
            await ctx.send("❌ Failed to post standup.", ephemeral=True)

    @standup.command(name="skip", description="Skip today's standup with reason")
    @app_commands.describe(reason="Reason for skipping")
    async def standup_skip(self, ctx: commands.Context, *, reason: str = "No reason provided"):
        """Skip standup"""
        try:
            today = datetime.utcnow().date()
            
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        # Check if already posted today
                        cur.execute("""
                            SELECT id FROM standup_posts 
                            WHERE user_id = %s AND guild_id = %s AND post_date = %s
                        """, (ctx.author.id, ctx.guild.id, today))
                        
                        if cur.fetchone():
                            await ctx.send("❌ You've already posted your standup today!", ephemeral=True)
                            return
                        
                        # Save skip record
                        cur.execute("""
                            INSERT INTO standup_posts (user_id, guild_id, channel_id, post_date, content, skipped, skip_reason)
                            VALUES (%s, %s, %s, %s, %s, TRUE, %s)
                        """, (ctx.author.id, ctx.guild.id, ctx.channel.id, today, "Skipped", reason))
                        conn.commit()
                    
                    embed = discord.Embed(
                        title="⏭️ Standup Skipped",
                        description=f"**Reason:** {reason}",
                        color=discord.Color.orange()
                    )
                    embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
                    embed.set_footer(text=f"Skipped on {today}")
                    
                    await ctx.send(embed=embed)
                else:
                    await ctx.send("❌ Database connection unavailable. Please try again later.", ephemeral=True)
                    
        except Exception as e:
            logger.error(f"standup_skip error: {e}")
            await ctx.send("❌ Failed to skip standup.", ephemeral=True)

    @standup.command(name="template", description="Customize standup format")
    @app_commands.describe(template="New standup template")
    async def standup_template(self, ctx: commands.Context, *, template: str):
        """Update standup template"""
        try:
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        # Update template
                        cur.execute("""
                            UPDATE standup_schedules 
                            SET template = %s 
                            WHERE guild_id = %s AND active = TRUE
                        """, (template, ctx.guild.id))
                        conn.commit()
                        
                        # Update in-memory cache
                        if ctx.guild.id in self.standup_schedules:
                            self.standup_schedules[ctx.guild.id]['template'] = template
                    
                    embed = discord.Embed(
                        title="✅ Standup Template Updated",
                        description=f"**New Template:**\n{template}",
                        color=discord.Color.green()
                    )
                    await ctx.send(embed=embed)
                else:
                    await ctx.send("❌ Database connection unavailable. Please try again later.", ephemeral=True)
                    
        except Exception as e:
            logger.error(f"standup_template error: {e}")
            await ctx.send("❌ Failed to update template.", ephemeral=True)

    @standup.command(name="list", description="View standup history")
    @app_commands.describe(days="Number of days to show (default: 7)")
    async def standup_list(self, ctx: commands.Context, days: int = 7):
        """List standup history"""
        try:
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            SELECT user_id, post_date, content, skipped, skip_reason, created_at
                            FROM standup_posts 
                            WHERE guild_id = %s AND post_date >= %s
                            ORDER BY post_date DESC, created_at DESC
                            LIMIT 20
                        """, (ctx.guild.id, datetime.utcnow().date() - timedelta(days=days)))
                        rows = cur.fetchall()
                    
                    if not rows:
                        await ctx.send("📝 No standup posts found.")
                        return
                    
                    embed = discord.Embed(
                        title=f"📋 Standup History (Last {days} days)",
                        color=discord.Color.blue()
                    )
                    
                    for user_id, post_date, content, skipped, skip_reason, created_at in rows[:10]:
                        user = self.bot.get_user(user_id)
                        user_name = user.display_name if user else f"User {user_id}"
                        
                        if skipped:
                            embed.add_field(
                                name=f"⏭️ {user_name} - {post_date}",
                                value=f"*Skipped: {skip_reason}*",
                                inline=False
                            )
                        else:
                            embed.add_field(
                                name=f"📋 {user_name} - {post_date}",
                                value=content[:200] + "..." if len(content) > 200 else content,
                                inline=False
                            )
                    
                    await ctx.send(embed=embed)
                else:
                    await ctx.send("❌ Database connection unavailable. Please try again later.", ephemeral=True)
                    
        except Exception as e:
            logger.error(f"standup_list error: {e}")
            await ctx.send("❌ Failed to list standups.", ephemeral=True)

    # ===== COLLABORATION COMMANDS =====

    @commands.hybrid_command(name="sync", description="Request a sync meeting with someone")
    @app_commands.describe(
        user="User to sync with",
        message="Optional message for the sync request"
    )
    async def sync_request(self, ctx: commands.Context, user: discord.Member, *, message: str = None):
        """Request sync meeting"""
        try:
            if user == ctx.author:
                await ctx.send("❌ You can't sync with yourself!", ephemeral=True)
                return
            
            request_id = f"SYNC{int(datetime.utcnow().timestamp())}"
            
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO sync_requests (request_id, requester_id, target_id, guild_id, channel_id, message)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (request_id, ctx.author.id, user.id, ctx.guild.id, ctx.channel.id, message))
                        conn.commit()
                    
                    embed = discord.Embed(
                        title="🤝 Sync Request Sent",
                        description=f"**From:** {ctx.author.mention}\n**To:** {user.mention}",
                        color=discord.Color.blue()
                    )
                    if message:
                        embed.add_field(name="Message", value=message, inline=False)
                    embed.set_footer(text=f"Request ID: {request_id}")
                    
                    await ctx.send(embed=embed)
                    
                    # Send DM to target user
                    try:
                        dm_embed = discord.Embed(
                            title="🤝 Sync Request",
                            description=f"{ctx.author.mention} wants to sync with you!",
                            color=discord.Color.blue()
                        )
                        if message:
                            dm_embed.add_field(name="Message", value=message, inline=False)
                        dm_embed.add_field(name="Server", value=ctx.guild.name, inline=True)
                        dm_embed.add_field(name="Channel", value=ctx.channel.mention, inline=True)
                        dm_embed.set_footer(text=f"Request ID: {request_id}")
                        
                        await user.send(embed=dm_embed)
                    except discord.Forbidden:
                        pass  # User has DMs disabled
                else:
                    await ctx.send("❌ Database connection unavailable. Please try again later.", ephemeral=True)
                    
        except Exception as e:
            logger.error(f"sync_request error: {e}")
            await ctx.send("❌ Failed to send sync request.", ephemeral=True)

    @commands.hybrid_command(name="pair", description="Start pair programming session")
    @app_commands.describe(
        user="User to pair with",
        topic="Optional topic for the session"
    )
    async def pair_start(self, ctx: commands.Context, user: discord.Member, *, topic: str = None):
        """Start pair programming session"""
        try:
            if user == ctx.author:
                await ctx.send("❌ You can't pair with yourself!", ephemeral=True)
                return
            
            session_id = f"PAIR{int(datetime.utcnow().timestamp())}"
            
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO pair_sessions (session_id, user1_id, user2_id, guild_id, channel_id, start_time, topic)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (session_id, ctx.author.id, user.id, ctx.guild.id, ctx.channel.id, datetime.utcnow(), topic))
                        conn.commit()
                    
                    # Store in memory for quick access
                    self.pair_sessions[session_id] = {
                        'user1': ctx.author.id,
                        'user2': user.id,
                        'start_time': datetime.utcnow(),
                        'topic': topic
                    }
                    
                    embed = discord.Embed(
                        title="👥 Pair Programming Started",
                        description=f"**Pair:** {ctx.author.mention} & {user.mention}",
                        color=discord.Color.green()
                    )
                    if topic:
                        embed.add_field(name="Topic", value=topic, inline=False)
                    embed.set_footer(text=f"Session ID: {session_id}")
                    
                    await ctx.send(embed=embed)
                else:
                    await ctx.send("❌ Database connection unavailable. Please try again later.", ephemeral=True)
                    
        except Exception as e:
            logger.error(f"pair_start error: {e}")
            await ctx.send("❌ Failed to start pair session.", ephemeral=True)

    @commands.hybrid_command(name="pair", description="End pair programming session")
    async def pair_end(self, ctx: commands.Context):
        """End pair programming session"""
        try:
            # Find active session for this user
            active_session = None
            for session_id, session_data in self.pair_sessions.items():
                if session_data['user1'] == ctx.author.id or session_data['user2'] == ctx.author.id:
                    active_session = session_id
                    break
            
            if not active_session:
                await ctx.send("❌ No active pair programming session found!", ephemeral=True)
                return
            
            session_data = self.pair_sessions[active_session]
            start_time = session_data['start_time']
            duration = datetime.utcnow() - start_time
            duration_minutes = int(duration.total_seconds() / 60)
            
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            UPDATE pair_sessions 
                            SET end_time = %s, duration_minutes = %s
                            WHERE session_id = %s
                        """, (datetime.utcnow(), duration_minutes, active_session))
                        conn.commit()
                    
                    # Remove from memory
                    del self.pair_sessions[active_session]
                    
                    user1 = self.bot.get_user(session_data['user1'])
                    user2 = self.bot.get_user(session_data['user2'])
                    
                    embed = discord.Embed(
                        title="✅ Pair Programming Ended",
                        description=f"**Pair:** {user1.mention if user1 else 'Unknown'} & {user2.mention if user2 else 'Unknown'}",
                        color=discord.Color.orange()
                    )
                    embed.add_field(name="Duration", value=f"{duration_minutes} minutes", inline=True)
                    if session_data['topic']:
                        embed.add_field(name="Topic", value=session_data['topic'], inline=True)
                    embed.set_footer(text=f"Session ID: {active_session}")
                    
                    await ctx.send(embed=embed)
                else:
                    await ctx.send("❌ Database connection unavailable. Please try again later.", ephemeral=True)
                    
        except Exception as e:
            logger.error(f"pair_end error: {e}")
            await ctx.send("❌ Failed to end pair session.", ephemeral=True)

async def setup(bot: commands.Bot):
    """Setup function for the cog"""
    try:
        get_db_connection_func = getattr(bot, "get_db_connection", None)
        if not get_db_connection_func:
            logger.error("❌ get_db_connection not found on bot instance")
            return
        
        await bot.add_cog(Standup(bot, get_db_connection_func))
        logger.info("✅ Standup/Collaboration cog loaded successfully")
    except Exception as e:
        logger.error(f"❌ Failed to setup Standup/Collaboration cog: {e}")
        import traceback
        traceback.print_exc()
