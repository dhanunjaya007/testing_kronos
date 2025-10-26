import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class Gamification(commands.Cog):
    def __init__(self, bot, get_db_connection_func):
        self.bot = bot
        self.get_db_connection = get_db_connection_func

    # ===== XP & Level =====

    @commands.hybrid_command(name="xp_view", description="View XP and level of a user")
    @app_commands.describe(user="User to view (defaults to yourself)")
    async def xp_view(self, ctx: commands.Context, user: Optional[discord.Member] = None):
        target = user or ctx.author
        try:
            with self.get_db_connection() as conn:
                if not conn:
                    await ctx.send("❌ Database unavailable.")
                    return
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT xp, level FROM user_xp_levels WHERE user_id = %s AND guild_id = %s
                    """, (target.id, ctx.guild.id))
                    row = cur.fetchone()
                    
            if not row:
                await ctx.send(f"ℹ️ No XP data found for {target.display_name}")
                return
            xp, level = row
            embed = discord.Embed(
                title=f"📊 XP and Level for {target.display_name}",
                color=discord.Color.gold()
            )
            embed.add_field(name="Level", value=str(level))
            embed.add_field(name="XP", value=str(xp))
            embed.set_thumbnail(url=target.avatar.url if target.avatar else target.default_avatar.url)
            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"xp_view error: {e}")
            await ctx.send("❌ Failed to fetch XP data.")

    @commands.hybrid_command(name="xp_leaderboard", description="Show XP leaderboard")
    async def xp_leaderboard(self, ctx: commands.Context):
        try:
            with self.get_db_connection() as conn:
                if not conn:
                    await ctx.send("❌ Database unavailable.")
                    return
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT user_id, xp, level FROM user_xp_levels
                        WHERE guild_id = %s ORDER BY xp DESC LIMIT 10
                    """, (ctx.guild.id,))
                    rows = cur.fetchall()
            
            embed = discord.Embed(
                title="🏆 XP Leaderboard",
                color=discord.Color.gold()
            )
            for idx, (user_id, xp, level) in enumerate(rows, start=1):
                user = self.bot.get_user(user_id)
                name = user.display_name if user else f"User {user_id}"
                embed.add_field(name=f"{idx}. {name}", value=f"Level {level} - {xp} XP", inline=False)
            
            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"xp_leaderboard error: {e}")
            await ctx.send("❌ Failed to fetch leaderboard.")

    @commands.hybrid_command(name="level_info", description="View level requirements and rewards")
    async def level_info(self, ctx: commands.Context):
        # Custom level info can be fetched from DB or static here
        info_text = (
            "XP required per level increases by 100.\n"
            "Rewards:\n"
            "- Level 5: Bronze badge\n"
            "- Level 10: Silver badge\n"
            "- Level 20: Gold badge"
        )
        embed = discord.Embed(
            title="📈 Level Info",
            description=info_text,
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    # ===== Badges =====

    @commands.hybrid_command(name="badge_list", description="View earned badges")
    @app_commands.describe(user="User to view badges for (default yourself)")
    async def badge_list(self, ctx: commands.Context, user: Optional[discord.Member] = None):
        target = user or ctx.author
        try:
            with self.get_db_connection() as conn:
                if not conn:
                    await ctx.send("❌ Database unavailable.")
                    return
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT badge_name, date_earned FROM user_badges
                        WHERE user_id = %s AND guild_id = %s
                    """, (target.id, ctx.guild.id))
                    rows = cur.fetchall()
            
            if not rows:
                await ctx.send(f"ℹ️ {target.display_name} has not earned any badges yet.")
                return
            
            embed = discord.Embed(
                title=f"🏅 Badges for {target.display_name}",
                color=discord.Color.purple()
            )
            for badge_name, date_earned in rows:
                embed.add_field(name=badge_name, value=date_earned.strftime("%Y-%m-%d"), inline=True)

            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"badge_list error: {e}")
            await ctx.send("❌ Failed to fetch badges.")

    # ===== Challenges =====

    @commands.hybrid_command(name="challenge_create", description="Create a coding challenge")
    @app_commands.describe(title="Challenge title", description="Description", xp_reward="XP reward")
    async def challenge_create(self, ctx: commands.Context, title: str, description: str, xp_reward: int):
        try:
            challenge_id = f"CH{int(datetime.utcnow().timestamp())}"
            with self.get_db_connection() as conn:
                if not conn:
                    await ctx.send("❌ Database unavailable.")
                    return
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO challenges (challenge_id, title, description, xp_reward, guild_id)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (challenge_id, title, description, xp_reward, ctx.guild.id))
                    conn.commit()
            await ctx.send(f"✅ Challenge `{challenge_id}` created.")
        except Exception as e:
            logger.error(f"challenge_create error: {e}")
            await ctx.send("❌ Failed to create challenge.")

    @commands.hybrid_command(name="challenge_list", description="View active challenges")
    async def challenge_list(self, ctx: commands.Context):
        try:
            with self.get_db_connection() as conn:
                if not conn:
                    await ctx.send("❌ Database unavailable.")
                    return
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT challenge_id, title, xp_reward FROM challenges WHERE guild_id = %s
                    """, (ctx.guild.id,))
                    rows = cur.fetchall()
            if not rows:
                await ctx.send("ℹ️ No active challenges.")
                return
            embed = discord.Embed(
                title="📝 Active Challenges",
                color=discord.Color.teal()
            )
            for cid, title, xp_reward in rows:
                embed.add_field(name=f"{cid}: {title}", value=f"Reward: {xp_reward} XP", inline=False)
            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"challenge_list error: {e}")
            await ctx.send("❌ Failed to fetch challenges.")

    @commands.hybrid_command(name="challenge_complete", description="Submit challenge completion")
    @app_commands.describe(challenge_id="Challenge ID to complete")
    async def challenge_complete(self, ctx: commands.Context, challenge_id: str):
        try:
            user_id = ctx.author.id
            guild_id = ctx.guild.id
            with self.get_db_connection() as conn:
                if not conn:
                    await ctx.send("❌ Database unavailable.")
                    return
                with conn.cursor() as cur:
                    cur.execute("SELECT xp_reward FROM challenges WHERE challenge_id = %s AND guild_id = %s", (challenge_id, guild_id))
                    row = cur.fetchone()
                    if not row:
                        await ctx.send("❌ Challenge not found.")
                        return
                    xp_reward = row[0]
                    # Record completion and add XP; Simplified logic here
                    cur.execute("""
                        INSERT INTO completed_challenges (user_id, challenge_id, guild_id, completed_at)
                        VALUES (%s, %s, %s, NOW())
                        ON CONFLICT DO NOTHING
                    """, (user_id, challenge_id, guild_id))
                    # Update user XP / level
                    cur.execute("""
                        INSERT INTO user_xp_levels (user_id, guild_id, xp, level)
                        VALUES (%s, %s, %s, 1)
                        ON CONFLICT (user_id, guild_id)
                        DO UPDATE SET xp = user_xp_levels.xp + %s 
                    """, (user_id, guild_id, xp_reward, xp_reward))
                    conn.commit()
            await ctx.send(f"✅ Challenge `{challenge_id}` completed! You earned {xp_reward} XP.")
        except Exception as e:
            logger.error(f"challenge_complete error: {e}")
            await ctx.send("❌ Failed to complete challenge.")

    # ===== Coding streak =====

    @commands.hybrid_command(name="streak_view", description="View coding streak")
    @app_commands.describe(user="User to view streak for (default self)")
    async def streak_view(self, ctx: commands.Context, user: Optional[discord.Member] = None):
        target = user or ctx.author
        try:
            with self.get_db_connection() as conn:
                if not conn:
                    await ctx.send("❌ Database unavailable.")
                    return
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT current_streak, longest_streak FROM user_streaks WHERE user_id = %s AND guild_id = %s
                    """, (target.id, ctx.guild.id))
                    row = cur.fetchone()
            if not row:
                await ctx.send(f"ℹ️ No streak data for {target.display_name}")
                return
            current_streak, longest_streak = row
            embed = discord.Embed(
                title=f"🔥 Coding Streak for {target.display_name}",
                color=discord.Color.orange()
            )
            embed.add_field(name="Current Streak (days)", value=str(current_streak))
            embed.add_field(name="Longest Streak", value=str(longest_streak))
            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"streak_view error: {e}")
            await ctx.send("❌ Failed to fetch streak.")

    # ===== Kudos =====

    @commands.hybrid_command(name="kudos", description="Give kudos points to a user")
    @app_commands.describe(user="User to give kudos")
    async def kudos(self, ctx: commands.Context, user: discord.Member):
        if user.bot:
            await ctx.send("❌ Cannot give kudos to bots.", ephemeral=True)
            return
        try:
            with self.get_db_connection() as conn:
                if not conn:
                    await ctx.send("❌ Database unavailable.")
                    return
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO user_kudos (user_id, guild_id, kudos)
                        VALUES (%s, %s, 1)
                        ON CONFLICT (user_id, guild_id) 
                        DO UPDATE SET kudos = user_kudos.kudos + 1
                    """, (user.id, ctx.guild.id))
                    conn.commit()
            await ctx.send(f"👏 Kudos given to {user.mention}!")
        except Exception as e:
            logger.error(f"kudos error: {e}")
            await ctx.send("❌ Failed to give kudos.")

    @commands.hybrid_command(name="kudos_leaderboard", description="View kudos leaderboard")
    async def kudos_leaderboard(self, ctx: commands.Context):
        try:
            with self.get_db_connection() as conn:
                if not conn:
                    await ctx.send("❌ Database unavailable.")
                    return
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT user_id, kudos FROM user_kudos WHERE guild_id = %s ORDER BY kudos DESC LIMIT 10
                    """, (ctx.guild.id,))
                    rows = cur.fetchall()
            embed = discord.Embed(
                title="🏅 Kudos Leaderboard",
                color=discord.Color.gold()
            )
            for idx, (user_id, kudos) in enumerate(rows, start=1):
                user = self.bot.get_user(user_id)
                name = user.display_name if user else f"User {user_id}"
                embed.add_field(name=f"{idx}. {name}", value=f"Kudos: {kudos}", inline=False)
            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"kudos_leaderboard error: {e}")
            await ctx.send("❌ Failed to fetch kudos leaderboard.")

async def setup(bot: commands.Bot):
    get_db_connection_func = getattr(bot, "get_db_connection", None)
    if not get_db_connection_func:
        logger.error("❌ get_db_connection not found on bot instance")
        return
    await bot.add_cog(Gamification(bot, get_db_connection_func))
    logger.info("✅ Gamification cog loaded successfully")
