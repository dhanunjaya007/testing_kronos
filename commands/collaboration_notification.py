import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class TeamCollaboration(commands.Cog):
    def __init__(self, bot, get_db_connection_func):
        self.bot = bot
        self.get_db_connection = get_db_connection_func
        self.notification_settings = {}  # in-memory cache for notification prefs

    @commands.hybrid_command(name="notify_task", description="Notify someone about a task")
    @app_commands.describe(task_id="Task ID", user="User to notify", message="Optional message")
    async def notify_task(self, ctx: commands.Context, task_id: str, user: discord.Member, *, message: Optional[str] = None):
        desc = message or "You have a new notification about a task."
        mention = user.mention
        await ctx.send(f"{mention}, 🛎 {desc} (Task ID: {task_id})")

    @commands.hybrid_command(name="notify_standup", description="Schedule daily standup reminder")
    @app_commands.describe(time="Standup reminder time (HH:MM 24h)")
    async def notify_standup(self, ctx: commands.Context, time: str):
        # Validate time format
        try:
            datetime.strptime(time, "%H:%M")
        except ValueError:
            await ctx.send("❌ Invalid time format, expected HH:MM (24h).", ephemeral=True)
            return
        # Save schedule - simplistic in-memory or DB placeholder
        self.notification_settings['standup_time'] = time
        await ctx.send(f"⏰ Daily standup reminder scheduled at {time} UTC.")

    @commands.hybrid_command(name="notify_settings", description="Configure notification preferences")
    async def notify_settings(self, ctx: commands.Context):
        # Retrieve and display user or server-wide settings: placeholder
        settings = self.notification_settings or {}
        embed = discord.Embed(
            title="🔔 Notification Settings",
            description=str(settings) or "No settings configured.",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="notify_mute", description="Mute specific notification type")
    @app_commands.describe(notification_type="Type to mute (task/meeting/reminder)")
    async def notify_mute(self, ctx: commands.Context, notification_type: str):
        # Store muted types in memory or DB (simple example)
        muted = self.notification_settings.setdefault('muted', set())
        muted.add(notification_type.lower())
        await ctx.send(f"🔕 Muted notifications of type: {notification_type}")

    @commands.hybrid_command(name="notify_unmute", description="Unmute specific notification type")
    @app_commands.describe(notification_type="Type to unmute")
    async def notify_unmute(self, ctx: commands.Context, notification_type: str):
        muted = self.notification_settings.setdefault('muted', set())
        if notification_type.lower() in muted:
            muted.remove(notification_type.lower())
            await ctx.send(f"🔔 Unmuted notifications of type: {notification_type}")
        else:
            await ctx.send(f"ℹ️ Notification type {notification_type} is not muted.")

    @commands.hybrid_command(name="status_set", description="Set your work status")
    @app_commands.describe(status_message="Your current status message")
    async def status_set(self, ctx: commands.Context, *, status_message: str):
        try:
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO user_status (user_id, guild_id, status_message, updated_at)
                            VALUES (%s, %s, %s, NOW())
                            ON CONFLICT (user_id, guild_id)
                            DO UPDATE SET status_message = EXCLUDED.status_message, updated_at = NOW()
                        """, (ctx.author.id, ctx.guild.id, status_message))
                        conn.commit()
            await ctx.send(f"✅ Status updated to: {status_message}")
        except Exception as e:
            logger.error(f"status_set error: {e}")
            await ctx.send("❌ Failed to update status.")

    @commands.hybrid_command(name="status_team", description="View all team members' statuses")
    async def status_team(self, ctx: commands.Context):
        try:
            with self.get_db_connection() as conn:
                if not conn:
                    await ctx.send("❌ Database unavailable.")
                    return
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT user_id, status_message, updated_at FROM user_status WHERE guild_id = %s
                    """, (ctx.guild.id,))
                    rows = cur.fetchall()
            if not rows:
                await ctx.send("ℹ️ No status updates found.")
                return
            embed = discord.Embed(
                title=f"👥 Team Statuses for {ctx.guild.name}",
                color=discord.Color.blue()
            )
            for user_id, status_msg, updated_at in rows:
                user = self.bot.get_user(user_id)
                name = user.display_name if user else f"User {user_id}"
                embed.add_field(name=name, value=f"{status_msg} (updated {updated_at.strftime('%Y-%m-%d %H:%M')})", inline=False)
            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"status_team error: {e}")
            await ctx.send("❌ Failed to fetch team statuses.")

    @commands.hybrid_command(name="review_request", description="Request code/task review")
    @app_commands.describe(task_id="Task ID", reviewer="Reviewer to request")
    async def review_request(self, ctx: commands.Context, task_id: str, reviewer: discord.Member):
        await ctx.send(f"🔍 {reviewer.mention}, you have been requested to review Task #{task_id} by {ctx.author.mention}!")

    @commands.hybrid_command(name="review_complete", description="Mark review as done")
    @app_commands.describe(task_id="Task ID")
    async def review_complete(self, ctx: commands.Context, task_id: str):
        await ctx.send(f"✅ Review for Task #{task_id} marked as complete by {ctx.author.mention}!")

    @commands.hybrid_command(name="review_assign", description="Assign code reviewer")
    @app_commands.describe(task_id="Task ID", reviewer="Reviewer to assign")
    async def review_assign(self, ctx: commands.Context, task_id: str, reviewer: discord.Member):
        await ctx.send(f"📝 Task #{task_id} assigned to {reviewer.mention} for code review.")

    @commands.hybrid_command(name="subscribe", description="Subscribe to event notifications")
    @app_commands.describe(event_type="Event to subscribe to")
    async def subscribe(self, ctx: commands.Context, event_type: str):
        # Placeholder: Add user subscription to DB or memory
        await ctx.send(f"🔔 You have subscribed to `{event_type}` notifications.")

    @commands.hybrid_command(name="unsubscribe", description="Unsubscribe from events")
    @app_commands.describe(event_type="Event to unsubscribe from")
    async def unsubscribe(self, ctx: commands.Context, event_type: str):
        # Placeholder: Remove subscription
        await ctx.send(f"🔕 You have unsubscribed from `{event_type}` notifications.")

async def setup(bot: commands.Bot):
    get_db_connection_func = getattr(bot, "get_db_connection", None)
    if not get_db_connection_func:
        logger.error("❌ get_db_connection not found on bot instance")
        return
    await bot.add_cog(TeamCollaboration(bot, get_db_connection_func))
    logger.info("✅ TeamCollaboration cog loaded successfully")
