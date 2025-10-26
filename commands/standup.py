import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class Standup(commands.Cog):
    def __init__(self, bot, get_db_connection_func):
        self.bot = bot
        self.get_db_connection = get_db_connection_func
        self.init_db_tables()

    def init_db_tables(self):
        """Initialize standup tables"""
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
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                        """)
                        
                        # User status table
                        cur.execute("""
                            CREATE TABLE IF NOT EXISTS user_status (
                                id SERIAL PRIMARY KEY,
                                user_id BIGINT NOT NULL,
                                guild_id BIGINT NOT NULL,
                                status_message TEXT,
                                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                UNIQUE(user_id, guild_id)
                            )
                        """)
                        
                        conn.commit()
                    logger.info("✅ Standup tables initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize standup tables: {e}")

    @commands.hybrid_command(name="standup", description="Submit daily standup")
    @app_commands.describe(
        yesterday="What you did yesterday",
        today="What you'll do today",
        blockers="Any blockers (optional)"
    )
    async def standup(self, ctx: commands.Context, yesterday: str, today: str, blockers: Optional[str] = "None"):
        """Submit standup"""
        try:
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO standup_responses (user_id, guild_id, yesterday, today, blockers)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (ctx.author.id, ctx.guild.id, yesterday, today, blockers))
                        conn.commit()
            
            embed = discord.Embed(
                title="📋 Daily Standup",
                color=discord.Color.blue()
            )
            embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
            embed.add_field(name="Yesterday", value=yesterday, inline=False)
            embed.add_field(name="Today", value=today, inline=False)
            embed.add_field(name="Blockers", value=blockers, inline=False)
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"standup error: {e}")
            await ctx.send("❌ Failed to submit standup.", ephemeral=True)

    @commands.hybrid_command(name="standup_summary", description="View today's standup summary")
    async def standup_summary(self, ctx: commands.Context):
        """View standup summary"""
        try:
            today = datetime.utcnow().date()
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            SELECT user_id, yesterday, today, blockers 
                            FROM standup_responses 
                            WHERE guild_id = %s AND created_at::date = %s
                            ORDER BY created_at DESC
                        """, (ctx.guild.id, today))
                        rows = cur.fetchall()
            
            if not rows:
                await ctx.send("📋 No standups submitted today.")
                return
            
            embed = discord.Embed(
                title=f"📋 Today's Standup Summary ({today})",
                color=discord.Color.blue()
            )
            
            for user_id, yesterday, today_text, blockers in rows:
                user = self.bot.get_user(user_id)
                name = user.display_name if user else f"User {user_id}"
                
                value = f"**Yesterday:** {yesterday[:100]}\n**Today:** {today_text[:100]}"
                if blockers and blockers.lower() != "none":
                    value += f"\n**Blockers:** {blockers[:100]}"
                
                embed.add_field(name=name, value=value, inline=False)
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"standup_summary error: {e}")
            await ctx.send("❌ Failed to get standup summary.", ephemeral=True)

async def setup(bot: commands.Bot):
    """Setup function for the cog"""
    try:
        get_db_connection_func = getattr(bot, "get_db_connection", None)
        if not get_db_connection_func:
            logger.error("❌ get_db_connection not found on bot instance")
            return
        
        await bot.add_cog(Standup(bot, get_db_connection_func))
        logger.info("✅ Standup cog loaded successfully")
    except Exception as e:
        logger.error(f"❌ Failed to setup Standup cog: {e}")
        import traceback
        traceback.print_exc()
