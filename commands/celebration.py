import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
import logging
from typing import Optional, Literal
import random

logger = logging.getLogger(__name__)

class Celebration(commands.Cog):
    def __init__(self, bot, get_db_connection_func):
        self.bot = bot
        self.get_db_connection = get_db_connection_func
        self.init_db_tables()

    def init_db_tables(self):
        """Initialize celebration tables"""
        try:
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        # Celebrations table
                        cur.execute("""
                            CREATE TABLE IF NOT EXISTS celebrations (
                                id SERIAL PRIMARY KEY,
                                celebrator_id BIGINT NOT NULL,
                                celebrated_id BIGINT NOT NULL,
                                guild_id BIGINT NOT NULL,
                                channel_id BIGINT NOT NULL,
                                reason TEXT,
                                celebration_type TEXT CHECK (celebration_type IN ('achievement', 'milestone', 'birthday', 'anniversary', 'other')),
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                        """)
                        
                        # Shoutouts table
                        cur.execute("""
                            CREATE TABLE IF NOT EXISTS shoutouts (
                                id SERIAL PRIMARY KEY,
                                giver_id BIGINT NOT NULL,
                                receiver_id BIGINT NOT NULL,
                                guild_id BIGINT NOT NULL,
                                channel_id BIGINT NOT NULL,
                                message TEXT NOT NULL,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                        """)
                        
                        # Team morale stats table
                        cur.execute("""
                            CREATE TABLE IF NOT EXISTS morale_stats (
                                id SERIAL PRIMARY KEY,
                                guild_id BIGINT NOT NULL,
                                user_id BIGINT NOT NULL,
                                celebrations_received INT DEFAULT 0,
                                shoutouts_received INT DEFAULT 0,
                                celebrations_given INT DEFAULT 0,
                                shoutouts_given INT DEFAULT 0,
                                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                UNIQUE(guild_id, user_id)
                            )
                        """)
                        
                        conn.commit()
                    logger.info("✅ Celebration tables initialized")
                else:
                    logger.warning("⚠️ Database connection not available - tables not initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize celebration tables: {e}")
            import traceback
            traceback.print_exc()

    # ===== CELEBRATION COMMANDS =====

    @commands.hybrid_command(name="celebrate", description="Celebrate team member's achievement")
    @app_commands.describe(
        user="User to celebrate",
        reason="Reason for celebration",
        type="Type of celebration"
    )
    async def celebrate(self, ctx: commands.Context, user: discord.Member, 
                      reason: str = "Great work!", 
                      type: Literal["achievement", "milestone", "birthday", "anniversary", "other"] = "achievement"):
        """Celebrate a team member"""
        try:
            if user == ctx.author:
                await ctx.send("❌ You can't celebrate yourself! Ask someone else to celebrate you! 😊", ephemeral=True)
                return
            
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        # Save celebration
                        cur.execute("""
                            INSERT INTO celebrations (celebrator_id, celebrated_id, guild_id, channel_id, reason, celebration_type)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (ctx.author.id, user.id, ctx.guild.id, ctx.channel.id, reason, type))
                        
                        # Update morale stats for receiver
                        cur.execute("""
                            INSERT INTO morale_stats (guild_id, user_id, celebrations_received)
                            VALUES (%s, %s, 1)
                            ON CONFLICT (guild_id, user_id) 
                            DO UPDATE SET 
                                celebrations_received = morale_stats.celebrations_received + 1,
                                last_updated = CURRENT_TIMESTAMP
                        """, (ctx.guild.id, user.id))
                        
                        # Update morale stats for giver
                        cur.execute("""
                            INSERT INTO morale_stats (guild_id, user_id, celebrations_given)
                            VALUES (%s, %s, 1)
                            ON CONFLICT (guild_id, user_id) 
                            DO UPDATE SET 
                                celebrations_given = morale_stats.celebrations_given + 1,
                                last_updated = CURRENT_TIMESTAMP
                        """, (ctx.guild.id, ctx.author.id))
                        
                        conn.commit()
                    
                    # Celebration messages and emojis
                    celebration_emojis = {
                        "achievement": ["🎉", "🏆", "⭐", "🌟", "💫"],
                        "milestone": ["🎊", "🎈", "🎁", "🏅", "🥇"],
                        "birthday": ["🎂", "🎈", "🎉", "🎁", "🎊"],
                        "anniversary": ["🎊", "💍", "🏆", "🎉", "🌟"],
                        "other": ["🎉", "🎊", "🌟", "⭐", "💫"]
                    }
                    
                    emoji = random.choice(celebration_emojis[type])
                    
                    embed = discord.Embed(
                        title=f"{emoji} Celebration! {emoji}",
                        description=f"**{ctx.author.display_name}** is celebrating **{user.display_name}**!",
                        color=discord.Color.gold()
                    )
                    embed.add_field(name="Reason", value=reason, inline=False)
                    embed.add_field(name="Type", value=type.title(), inline=True)
                    embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)
                    embed.set_footer(text=f"Celebrated by {ctx.author.display_name}")
                    
                    message = await ctx.send(embed=embed)
                    
                    # Add celebration reactions
                    celebration_reactions = ["🎉", "🎊", "🌟", "👏", "🔥"]
                    for reaction in celebration_reactions[:3]:  # Add first 3 reactions
                        try:
                            await message.add_reaction(reaction)
                        except:
                            pass
                else:
                    await ctx.send("❌ Database connection unavailable. Please try again later.", ephemeral=True)
                    
        except Exception as e:
            logger.error(f"celebrate error: {e}")
            await ctx.send("❌ Failed to celebrate team member.", ephemeral=True)

    @commands.hybrid_command(name="shoutout", description="Give a shoutout to team member")
    @app_commands.describe(
        user="User to give shoutout to",
        message="Shoutout message"
    )
    async def shoutout(self, ctx: commands.Context, user: discord.Member, *, message: str):
        """Give a shoutout to a team member"""
        try:
            if user == ctx.author:
                await ctx.send("❌ You can't give yourself a shoutout! Ask someone else to give you one! 😊", ephemeral=True)
                return
            
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        # Save shoutout
                        cur.execute("""
                            INSERT INTO shoutouts (giver_id, receiver_id, guild_id, channel_id, message)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (ctx.author.id, user.id, ctx.guild.id, ctx.channel.id, message))
                        
                        # Update morale stats for receiver
                        cur.execute("""
                            INSERT INTO morale_stats (guild_id, user_id, shoutouts_received)
                            VALUES (%s, %s, 1)
                            ON CONFLICT (guild_id, user_id) 
                            DO UPDATE SET 
                                shoutouts_received = morale_stats.shoutouts_received + 1,
                                last_updated = CURRENT_TIMESTAMP
                        """, (ctx.guild.id, user.id))
                        
                        # Update morale stats for giver
                        cur.execute("""
                            INSERT INTO morale_stats (guild_id, user_id, shoutouts_given)
                            VALUES (%s, %s, 1)
                            ON CONFLICT (guild_id, user_id) 
                            DO UPDATE SET 
                                shoutouts_given = morale_stats.shoutouts_given + 1,
                                last_updated = CURRENT_TIMESTAMP
                        """, (ctx.guild.id, ctx.author.id))
                        
                        conn.commit()
                    
                    # Shoutout emojis
                    shoutout_emojis = ["📢", "👏", "🌟", "💪", "🔥", "⭐", "🎯", "🚀"]
                    emoji = random.choice(shoutout_emojis)
                    
                    embed = discord.Embed(
                        title=f"{emoji} Shoutout! {emoji}",
                        description=f"**{ctx.author.display_name}** gives a shoutout to **{user.display_name}**!",
                        color=discord.Color.blue()
                    )
                    embed.add_field(name="Message", value=message, inline=False)
                    embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)
                    embed.set_footer(text=f"Shoutout by {ctx.author.display_name}")
                    
                    shoutout_message = await ctx.send(embed=embed)
                    
                    # Add shoutout reactions
                    shoutout_reactions = ["👏", "🔥", "💪", "⭐", "🎯"]
                    for reaction in shoutout_reactions[:3]:  # Add first 3 reactions
                        try:
                            await shoutout_message.add_reaction(reaction)
                        except:
                            pass
                else:
                    await ctx.send("❌ Database connection unavailable. Please try again later.", ephemeral=True)
                    
        except Exception as e:
            logger.error(f"shoutout error: {e}")
            await ctx.send("❌ Failed to give shoutout.", ephemeral=True)

    @commands.hybrid_command(name="morale", description="View team morale statistics")
    @app_commands.describe(user="User to check morale for (optional)")
    async def morale_stats(self, ctx: commands.Context, user: discord.Member = None):
        """View morale statistics"""
        try:
            target_user = user or ctx.author
            
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        # Get user's morale stats
                        cur.execute("""
                            SELECT celebrations_received, shoutouts_received, celebrations_given, shoutouts_given
                            FROM morale_stats 
                            WHERE guild_id = %s AND user_id = %s
                        """, (ctx.guild.id, target_user.id))
                        stats = cur.fetchone()
                        
                        if not stats:
                            await ctx.send(f"📊 No morale data found for {target_user.display_name}.", ephemeral=True)
                            return
                        
                        celebrations_received, shoutouts_received, celebrations_given, shoutouts_given = stats
                        
                        # Get recent celebrations and shoutouts
                        cur.execute("""
                            SELECT COUNT(*) FROM celebrations 
                            WHERE celebrated_id = %s AND guild_id = %s 
                            AND created_at >= %s
                        """, (target_user.id, ctx.guild.id, datetime.utcnow() - timedelta(days=30)))
                        recent_celebrations = cur.fetchone()[0]
                        
                        cur.execute("""
                            SELECT COUNT(*) FROM shoutouts 
                            WHERE receiver_id = %s AND guild_id = %s 
                            AND created_at >= %s
                        """, (target_user.id, ctx.guild.id, datetime.utcnow() - timedelta(days=30)))
                        recent_shoutouts = cur.fetchone()[0]
                        
                        embed = discord.Embed(
                            title=f"📊 Morale Stats - {target_user.display_name}",
                            color=discord.Color.green()
                        )
                        
                        embed.add_field(
                            name="🎉 Celebrations",
                            value=f"**Received:** {celebrations_received}\n**Given:** {celebrations_given}",
                            inline=True
                        )
                        embed.add_field(
                            name="📢 Shoutouts", 
                            value=f"**Received:** {shoutouts_received}\n**Given:** {shoutouts_given}",
                            inline=True
                        )
                        embed.add_field(
                            name="📈 Recent Activity (30 days)",
                            value=f"**Celebrations:** {recent_celebrations}\n**Shoutouts:** {recent_shoutouts}",
                            inline=False
                        )
                        
                        # Calculate morale score
                        total_positive = celebrations_received + shoutouts_received
                        total_given = celebrations_given + shoutouts_given
                        morale_score = min(100, (total_positive * 10) + (total_given * 5))
                        
                        embed.add_field(
                            name="🌟 Morale Score",
                            value=f"{morale_score}/100",
                            inline=True
                        )
                        
                        embed.set_thumbnail(url=target_user.avatar.url if target_user.avatar else target_user.default_avatar.url)
                        await ctx.send(embed=embed)
                else:
                    await ctx.send("❌ Database connection unavailable. Please try again later.", ephemeral=True)
                    
        except Exception as e:
            logger.error(f"morale_stats error: {e}")
            await ctx.send("❌ Failed to get morale stats.", ephemeral=True)

    @commands.hybrid_command(name="leaderboard", description="View team morale leaderboard")
    @app_commands.describe(period="Time period for leaderboard")
    async def morale_leaderboard(self, ctx: commands.Context, 
                               period: Literal["week", "month", "all"] = "month"):
        """View morale leaderboard"""
        try:
            # Calculate date filter
            if period == "week":
                date_filter = datetime.utcnow() - timedelta(days=7)
            elif period == "month":
                date_filter = datetime.utcnow() - timedelta(days=30)
            else:
                date_filter = None
            
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        if date_filter:
                            # Get top users by recent activity
                            cur.execute("""
                                SELECT user_id, 
                                       COUNT(CASE WHEN celebrated_id = user_id THEN 1 END) as celebrations,
                                       COUNT(CASE WHEN receiver_id = user_id THEN 1 END) as shoutouts
                                FROM (
                                    SELECT celebrated_id as user_id FROM celebrations 
                                    WHERE guild_id = %s AND created_at >= %s
                                    UNION ALL
                                    SELECT receiver_id as user_id FROM shoutouts 
                                    WHERE guild_id = %s AND created_at >= %s
                                ) activity
                                GROUP BY user_id
                                ORDER BY (celebrations + shoutouts) DESC
                                LIMIT 10
                            """, (ctx.guild.id, date_filter, ctx.guild.id, date_filter))
                        else:
                            # Get top users by all-time activity
                            cur.execute("""
                                SELECT user_id, celebrations_received, shoutouts_received
                                FROM morale_stats 
                                WHERE guild_id = %s
                                ORDER BY (celebrations_received + shoutouts_received) DESC
                                LIMIT 10
                            """, (ctx.guild.id,))
                        
                        rows = cur.fetchall()
                        
                        if not rows:
                            await ctx.send("📊 No morale data found for this period.", ephemeral=True)
                            return
                        
                        embed = discord.Embed(
                            title=f"🏆 Morale Leaderboard ({period.title()})",
                            color=discord.Color.gold()
                        )
                        
                        for i, row in enumerate(rows, 1):
                            user_id = row[0]
                            user = self.bot.get_user(user_id)
                            user_name = user.display_name if user else f"User {user_id}"
                            
                            if len(row) == 3:  # All-time data
                                celebrations, shoutouts = row[1], row[2]
                                total = celebrations + shoutouts
                            else:  # Recent data
                                celebrations, shoutouts = row[1], row[2]
                                total = celebrations + shoutouts
                            
                            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                            
                            embed.add_field(
                                name=f"{medal} {user_name}",
                                value=f"🎉 {celebrations} celebrations\n📢 {shoutouts} shoutouts\n**Total:** {total}",
                                inline=False
                            )
                        
                        await ctx.send(embed=embed)
                else:
                    await ctx.send("❌ Database connection unavailable. Please try again later.", ephemeral=True)
                    
        except Exception as e:
            logger.error(f"morale_leaderboard error: {e}")
            await ctx.send("❌ Failed to get leaderboard.", ephemeral=True)

async def setup(bot: commands.Bot):
    """Setup function for the cog"""
    try:
        get_db_connection_func = getattr(bot, "get_db_connection", None)
        if not get_db_connection_func:
            logger.error("❌ get_db_connection not found on bot instance")
            return
        
        await bot.add_cog(Celebration(bot, get_db_connection_func))
        logger.info("✅ Celebration cog loaded successfully")
    except Exception as e:
        logger.error(f"❌ Failed to setup Celebration cog: {e}")
        import traceback
        traceback.print_exc()
