import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta
import asyncio
import logging
import re

logger = logging.getLogger(__name__)

class CountdownTimer(commands.Cog):
    
    def __init__(self, bot, get_db_connection_func):
    self.bot = bot
    self.get_db_connection = get_db_connection_func
    self.countdowns = {}
    self.timers = {}
    self.check_reminders.start()  # FIXED

    def cog_unload(self):
    self.check_reminders.cancel()  # This stays the same


    async def check_reminders(self):
        while True:
            now = datetime.utcnow()
            to_remove = []
            for countdown_id, countdown in self.countdowns.items():
                end_time = countdown['end_time']
                channel = self.bot.get_channel(countdown['channel_id'])
                if not channel:
                    to_remove.append(countdown_id)
                    continue
                remaining = end_time - now
                if remaining.total_seconds() <= 0:
                    try:
                        await channel.send(f"⏰ Countdown **{countdown['event_name']}** ended!")
                    except Exception as e:
                        logger.error(f"Failed to send countdown end message: {e}")
                    to_remove.append(countdown_id)
                else:
                    try:
                        embed = discord.Embed(
                            title=f"⏳ Countdown: {countdown['event_name']}",
                            description=f"Ends in {str(remaining).split('.')[0]}",
                            color=discord.Color.dark_gold(),
                            timestamp=end_time
                        )
                        if 'message' not in countdown or countdown['message'] is None:
                            countdown['message'] = await channel.send(embed=embed)
                        else:
                            await countdown['message'].edit(embed=embed)
                    except Exception as e:
                        logger.error(f"Failed to update countdown message: {e}")
            for rm in to_remove:
                self.countdowns.pop(rm, None)
            await asyncio.sleep(10)

    @commands.hybrid_command(name="countdown_create", description="Create a temporary countdown message")
    @app_commands.describe(event_name="Name of the event", end_time="End time in format YYYY-MM-DD HH:MM UTC")
    async def countdown_create(self, ctx: commands.Context, event_name: str, end_time: str):
        try:
            target_time = datetime.strptime(end_time, "%Y-%m-%d %H:%M")
            if target_time <= datetime.utcnow():
                await ctx.send("❌ End time must be in the future.", ephemeral=True)
                return
        except ValueError:
            await ctx.send("❌ Invalid date format. Use YYYY-MM-DD HH:MM (24h, UTC).", ephemeral=True)
            return

        countdown_id = f"C{int(datetime.utcnow().timestamp())}"
        self.countdowns[countdown_id] = {
            'event_name': event_name,
            'end_time': target_time,
            'channel_id': ctx.channel.id,
            'message': None
        }
        await ctx.send(f"✅ Countdown `{countdown_id}` for **{event_name}** set until {target_time} UTC.")

    @commands.hybrid_command(name="countdown_list", description="View all active countdowns")
    async def countdown_list(self, ctx: commands.Context):
        if not self.countdowns:
            await ctx.send("ℹ️ No active countdowns.")
            return
        embed = discord.Embed(title="⏳ Active Countdowns", color=discord.Color.dark_gold())
        for cid, countdown in self.countdowns.items():
            remaining = countdown['end_time'] - datetime.utcnow()
            remaining_str = str(remaining).split('.')[0] if remaining.total_seconds() > 0 else "Ended"
            embed.add_field(name=f"{cid}: {countdown['event_name']}", value=f"Ends in: {remaining_str}", inline=False)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="countdown_delete", description="Delete a countdown")
    @app_commands.describe(countdown_id="ID of the countdown to delete")
    async def countdown_delete(self, ctx: commands.Context, countdown_id: str):
        countdown_id = countdown_id.upper()
        if countdown_id not in self.countdowns:
            await ctx.send(f"❌ Countdown `{countdown_id}` not found.", ephemeral=True)
            return
        self.countdowns.pop(countdown_id)
        await ctx.send(f"🗑️ Countdown `{countdown_id}` deleted.")

    @commands.hybrid_command(name="timer_start", description="Start a timer")
    @app_commands.describe(duration="Duration (e.g. 25m for 25 minutes)", message="Optional message to display after timer ends")
    async def timer_start(self, ctx: commands.Context, duration: str, *, message: str = "Timer ended!"):
        if ctx.author.id in self.timers:
            await ctx.send("❌ You already have an active timer. Use `/timer stop` to cancel it.", ephemeral=True)
            return
        try:
            match = re.match(r"(\d+)([smh])", duration)
            if not match:
                await ctx.send("❌ Invalid duration format. Use number followed by s/m/h, e.g., 10m.", ephemeral=True)
                return
            amount = int(match.group(1))
            unit = match.group(2)
            seconds = amount * (60 if unit == "m" else 3600 if unit == "h" else 1)
            if seconds <= 0:
                await ctx.send("❌ Duration must be positive.", ephemeral=True)
                return
        except Exception:
            await ctx.send("❌ Failed to parse duration.", ephemeral=True)
            return

        async def timer_task():
            try:
                await ctx.send(f"⏱ Timer started for {duration}.")
                await asyncio.sleep(seconds)
                await ctx.send(f"⏰ {ctx.author.mention} {message}")
            except Exception as e:
                logger.error(f"Error during timer: {e}")
            finally:
                self.timers.pop(ctx.author.id, None)

        self.timers[ctx.author.id] = self.bot.loop.create_task(timer_task())

    @commands.hybrid_command(name="timer_stop", description="Stop your active timer")
    async def timer_stop(self, ctx: commands.Context):
        task = self.timers.get(ctx.author.id)
        if not task:
            await ctx.send("❌ You have no active timer.", ephemeral=True)
            return
        task.cancel()
        self.timers.pop(ctx.author.id, None)
        await ctx.send("⏹ Your timer was stopped.")

async def setup(bot: commands.Bot):
    get_db_connection_func = getattr(bot, "get_db_connection", None)
    if not get_db_connection_func:
        logger.error("❌ get_db_connection not found on bot instance")
        return
    await bot.add_cog(CountdownTimer(bot, get_db_connection_func))
    logger.info("✅ CountdownTimer cog loaded successfully")
