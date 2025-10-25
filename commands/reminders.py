import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta
import asyncio
import re
import json
import os
from typing import Optional, Literal

class Reminders(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.reminders = {}  # {reminder_id: reminder_data}
        self.reminder_counter = 0
        self.reminders_file = 'reminders_data.json'
        self.load_reminders()
        self.check_reminders.start()

    def cog_unload(self):
        """Stop the reminder checker when cog is unloaded"""
        self.check_reminders.cancel()
        self.save_reminders()

    def load_reminders(self):
        """Load reminders from file"""
        try:
            if os.path.exists(self.reminders_file):
                with open(self.reminders_file, 'r') as f:
                    data = json.load(f)
                    self.reminders = data.get('reminders', {})
                    self.reminder_counter = data.get('counter', 0)
                    
                    # Convert string timestamps back to datetime
                    for rid, reminder in self.reminders.items():
                        reminder['trigger_time'] = datetime.fromisoformat(reminder['trigger_time'])
                        if reminder.get('next_trigger'):
                            reminder['next_trigger'] = datetime.fromisoformat(reminder['next_trigger'])
                    
                    print(f"✅ Loaded {len(self.reminders)} reminders from file")
        except Exception as e:
            print(f"⚠️ Could not load reminders: {e}")

    def save_reminders(self):
        """Save reminders to file"""
        try:
            # Convert datetime objects to ISO format strings for JSON
            save_data = {
                'counter': self.reminder_counter,
                'reminders': {}
            }
            
            for rid, reminder in self.reminders.items():
                reminder_copy = reminder.copy()
                reminder_copy['trigger_time'] = reminder['trigger_time'].isoformat()
                if reminder.get('next_trigger'):
                    reminder_copy['next_trigger'] = reminder['next_trigger'].isoformat()
                save_data['reminders'][rid] = reminder_copy
            
            with open(self.reminders_file, 'w') as f:
                json.dump(save_data, f, indent=2)
        except Exception as e:
            print(f"⚠️ Could not save reminders: {e}")

    def parse_time(self, time_str: str) -> Optional[datetime]:
        """Parse natural language time into datetime"""
        now = datetime.utcnow()
        time_str = time_str.lower().strip()

        # Patterns for "in X minutes/hours/days"
        in_pattern = re.match(r'in (\d+)\s*(minute|min|hour|hr|day|week)s?', time_str)
        if in_pattern:
            amount = int(in_pattern.group(1))
            unit = in_pattern.group(2)
            
            if unit in ['minute', 'min']:
                return now + timedelta(minutes=amount)
            elif unit in ['hour', 'hr']:
                return now + timedelta(hours=amount)
            elif unit == 'day':
                return now + timedelta(days=amount)
            elif unit == 'week':
                return now + timedelta(weeks=amount)

        # Patterns for "tomorrow", "today"
        if 'tomorrow' in time_str:
            base_time = now + timedelta(days=1)
            # Check for time specification
            time_match = re.search(r'(\d+):?(\d+)?\s*(am|pm)?', time_str)
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2)) if time_match.group(2) else 0
                period = time_match.group(3)
                
                if period == 'pm' and hour != 12:
                    hour += 12
                elif period == 'am' and hour == 12:
                    hour = 0
                    
                return base_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
            else:
                return base_time.replace(hour=9, minute=0, second=0, microsecond=0)

        if 'today' in time_str:
            time_match = re.search(r'(\d+):?(\d+)?\s*(am|pm)?', time_str)
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2)) if time_match.group(2) else 0
                period = time_match.group(3)
                
                if period == 'pm' and hour != 12:
                    hour += 12
                elif period == 'am' and hour == 12:
                    hour = 0
                    
                target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if target < now:
                    return None  # Time has passed today
                return target

        # Pattern for specific time (e.g., "3pm", "14:30")
        time_match = re.match(r'(\d+):?(\d+)?\s*(am|pm)?', time_str)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2)) if time_match.group(2) else 0
            period = time_match.group(3)
            
            if period == 'pm' and hour != 12:
                hour += 12
            elif period == 'am' and hour == 12:
                hour = 0
                
            target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if target < now:
                target += timedelta(days=1)  # Schedule for tomorrow
            return target

        return None

    def get_next_recurring_time(self, frequency: str, base_time: datetime) -> Optional[datetime]:
        """Calculate next trigger time for recurring reminders"""
        if frequency == 'daily':
            return base_time + timedelta(days=1)
        elif frequency == 'weekly':
            return base_time + timedelta(weeks=1)
        elif frequency == 'hourly':
            return base_time + timedelta(hours=1)
        return None

    @tasks.loop(seconds=30)
    async def check_reminders(self):
        """Check and trigger reminders"""
        now = datetime.utcnow()
        triggered = []

        for reminder_id, reminder in list(self.reminders.items()):
            if reminder['trigger_time'] <= now:
                # Send reminder
                try:
                    channel = self.bot.get_channel(reminder['channel_id'])
                    if channel:
                        user = self.bot.get_user(reminder['user_id'])
                        
                        embed = discord.Embed(
                            title="⏰ Reminder",
                            description=reminder['message'],
                            color=discord.Color.blue(),
                            timestamp=datetime.utcnow()
                        )
                        embed.set_footer(text=f"Reminder ID: {reminder_id}")
                        
                        if reminder.get('target_user_id'):
                            target_user = self.bot.get_user(reminder['target_user_id'])
                            if target_user:
                                embed.add_field(name="For", value=target_user.mention)
                        
                        await channel.send(
                            content=f"{user.mention if user else 'User'}'s reminder:",
                            embed=embed
                        )
                        
                        # Handle recurring reminders
                        if reminder.get('recurring'):
                            next_time = self.get_next_recurring_time(
                                reminder['frequency'],
                                reminder['trigger_time']
                            )
                            if next_time:
                                reminder['trigger_time'] = next_time
                                continue
                        
                        triggered.append(reminder_id)
                        
                except Exception as e:
                    print(f"Error triggering reminder {reminder_id}: {e}")
                    triggered.append(reminder_id)

        # Remove non-recurring triggered reminders
        for rid in triggered:
            if rid in self.reminders and not self.reminders[rid].get('recurring'):
                del self.reminders[rid]
        
        if triggered:
            self.save_reminders()

    @check_reminders.before_loop
    async def before_check_reminders(self):
        """Wait until bot is ready before checking reminders"""
        await self.bot.wait_until_ready()

    @commands.hybrid_group(name="reminder", description="Manage reminders")
    async def reminder(self, ctx: commands.Context):
        """Reminder management commands"""
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                title="⏰ Reminder Commands",
                description="Manage your reminders",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="Commands",
                value=(
                    "`/reminder set <time> <message>` - Set a reminder\n"
                    "`/reminder list` - View active reminders\n"
                    "`/reminder cancel <id>` - Cancel a reminder\n"
                    "`/reminder recurring <frequency> <time> <message>` - Set recurring reminder"
                ),
                inline=False
            )
            embed.add_field(
                name="Time Examples",
                value=(
                    "`in 30 minutes`, `in 2 hours`, `in 3 days`\n"
                    "`tomorrow 9am`, `today 5pm`\n"
                    "`14:30`, `3pm`"
                ),
                inline=False
            )
            await ctx.send(embed=embed)

    @reminder.command(name="set", description="Set a reminder")
    @app_commands.describe(
        time="When to remind (e.g., 'in 2 hours', 'tomorrow 9am')",
        message="Reminder message",
        target="Optional: mention a user or channel to send reminder to"
    )
    async def reminder_set(
        self, 
        ctx: commands.Context, 
        time: str, 
        *, 
        message: str
    ):
        """Set a reminder"""
        # Parse time
        trigger_time = self.parse_time(time)
        
        if not trigger_time:
            await ctx.send("❌ Could not parse time. Try: `in 30 minutes`, `tomorrow 9am`, `today 5pm`", ephemeral=True)
            return

        if trigger_time < datetime.utcnow():
            await ctx.send("❌ Cannot set reminder in the past!", ephemeral=True)
            return

        # Parse target (optional)
        target_user_id = None
        target_channel_id = ctx.channel.id
        
        # Check if message has mentions
        if ctx.message.mentions:
            target_user_id = ctx.message.mentions[0].id
        
        # Create reminder
        self.reminder_counter += 1
        reminder_id = f"R{self.reminder_counter}"
        
        self.reminders[reminder_id] = {
            'id': reminder_id,
            'user_id': ctx.author.id,
            'channel_id': target_channel_id,
            'target_user_id': target_user_id,
            'message': message,
            'trigger_time': trigger_time,
            'created_at': datetime.utcnow().isoformat(),
            'recurring': False
        }
        
        self.save_reminders()
        
        # Calculate time until reminder
        time_delta = trigger_time - datetime.utcnow()
        hours = int(time_delta.total_seconds() // 3600)
        minutes = int((time_delta.total_seconds() % 3600) // 60)
        
        embed = discord.Embed(
            title="✅ Reminder Set",
            description=f"I'll remind you: **{message}**",
            color=discord.Color.green()
        )
        embed.add_field(name="When", value=f"<t:{int(trigger_time.timestamp())}:F>")
        embed.add_field(name="In", value=f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m")
        embed.add_field(name="ID", value=reminder_id)
        
        if target_user_id:
            target_user = self.bot.get_user(target_user_id)
            embed.add_field(name="For", value=target_user.mention if target_user else "Unknown user")
        
        await ctx.send(embed=embed)

    @reminder.command(name="list", description="View all active reminders")
    async def reminder_list(self, ctx: commands.Context):
        """List all active reminders for the user"""
        user_reminders = [
            r for r in self.reminders.values() 
            if r['user_id'] == ctx.author.id
        ]
        
        if not user_reminders:
            await ctx.send("ℹ️ You have no active reminders.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title=f"⏰ Your Reminders ({len(user_reminders)})",
            color=discord.Color.blue()
        )
        
        # Sort by trigger time
        user_reminders.sort(key=lambda x: x['trigger_time'])
        
        for reminder in user_reminders[:10]:  # Show max 10
            time_delta = reminder['trigger_time'] - datetime.utcnow()
            hours = int(time_delta.total_seconds() // 3600)
            minutes = int((time_delta.total_seconds() % 3600) // 60)
            
            time_str = f"in {hours}h {minutes}m" if hours > 0 else f"in {minutes}m"
            if reminder.get('recurring'):
                time_str += f" (🔄 {reminder['frequency']})"
            
            embed.add_field(
                name=f"{reminder['id']}: {time_str}",
                value=reminder['message'][:100],
                inline=False
            )
        
        if len(user_reminders) > 10:
            embed.set_footer(text=f"Showing 10 of {len(user_reminders)} reminders")
        
        await ctx.send(embed=embed)

    @reminder.command(name="cancel", description="Cancel a reminder")
    @app_commands.describe(reminder_id="The ID of the reminder to cancel (e.g., R1)")
    async def reminder_cancel(self, ctx: commands.Context, reminder_id: str):
        """Cancel a reminder"""
        reminder_id = reminder_id.upper()
        
        if reminder_id not in self.reminders:
            await ctx.send(f"❌ Reminder `{reminder_id}` not found.", ephemeral=True)
            return
        
        reminder = self.reminders[reminder_id]
        
        # Check if user owns this reminder
        if reminder['user_id'] != ctx.author.id:
            await ctx.send("❌ You can only cancel your own reminders.", ephemeral=True)
            return
        
        message = reminder['message']
        del self.reminders[reminder_id]
        self.save_reminders()
        
        embed = discord.Embed(
            title="✅ Reminder Cancelled",
            description=f"Cancelled: **{message}**",
            color=discord.Color.red()
        )
        embed.add_field(name="ID", value=reminder_id)
        
        await ctx.send(embed=embed)

    @reminder.command(name="recurring", description="Set a recurring reminder")
    @app_commands.describe(
        frequency="How often (hourly, daily, weekly)",
        time="When to start (e.g., 'in 2 hours', '9am')",
        message="Reminder message"
    )
    async def reminder_recurring(
        self,
        ctx: commands.Context,
        frequency: Literal['hourly', 'daily', 'weekly'],
        time: str,
        *,
        message: str
    ):
        """Set a recurring reminder"""
        # Parse time
        trigger_time = self.parse_time(time)
        
        if not trigger_time:
            await ctx.send("❌ Could not parse time. Try: `in 30 minutes`, `9am`, `14:30`", ephemeral=True)
            return

        if trigger_time < datetime.utcnow():
            await ctx.send("❌ Cannot set reminder in the past!", ephemeral=True)
            return

        # Create reminder
        self.reminder_counter += 1
        reminder_id = f"R{self.reminder_counter}"
        
        self.reminders[reminder_id] = {
            'id': reminder_id,
            'user_id': ctx.author.id,
            'channel_id': ctx.channel.id,
            'target_user_id': None,
            'message': message,
            'trigger_time': trigger_time,
            'created_at': datetime.utcnow().isoformat(),
            'recurring': True,
            'frequency': frequency
        }
        
        self.save_reminders()
        
        # Calculate time until first reminder
        time_delta = trigger_time - datetime.utcnow()
        hours = int(time_delta.total_seconds() // 3600)
        minutes = int((time_delta.total_seconds() % 3600) // 60)
        
        embed = discord.Embed(
            title="✅ Recurring Reminder Set",
            description=f"I'll remind you: **{message}**",
            color=discord.Color.green()
        )
        embed.add_field(name="Frequency", value=f"🔄 {frequency.capitalize()}")
        embed.add_field(name="First reminder", value=f"<t:{int(trigger_time.timestamp())}:F>")
        embed.add_field(name="In", value=f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m")
        embed.add_field(name="ID", value=reminder_id)
        embed.set_footer(text="Use /reminder cancel to stop recurring reminder")
        
        await ctx.send(embed=embed)

    @reminder.command(name="clear", description="Clear all your reminders")
    async def reminder_clear(self, ctx: commands.Context):
        """Clear all reminders for the user"""
        user_reminders = [
            rid for rid, r in self.reminders.items() 
            if r['user_id'] == ctx.author.id
        ]
        
        if not user_reminders:
            await ctx.send("ℹ️ You have no active reminders.", ephemeral=True)
            return
        
        count = len(user_reminders)
        
        # Ask for confirmation
        embed = discord.Embed(
            title="⚠️ Clear All Reminders?",
            description=f"This will delete **{count}** reminder(s). This cannot be undone.",
            color=discord.Color.orange()
        )
        
        view = ConfirmView(ctx.author.id)
        message = await ctx.send(embed=embed, view=view)
        
        await view.wait()
        
        if view.value:
            for rid in user_reminders:
                del self.reminders[rid]
            self.save_reminders()
            
            await message.edit(
                embed=discord.Embed(
                    title="✅ Reminders Cleared",
                    description=f"Deleted {count} reminder(s).",
                    color=discord.Color.green()
                ),
                view=None
            )
        else:
            await message.edit(
                embed=discord.Embed(
                    title="❌ Cancelled",
                    description="No reminders were deleted.",
                    color=discord.Color.red()
                ),
                view=None
            )


class ConfirmView(discord.ui.View):
    """Confirmation view for clearing reminders"""
    def __init__(self, user_id: int):
        super().__init__(timeout=30)
        self.user_id = user_id
        self.value = None

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This isn't your confirmation!", ephemeral=True)
            return
        self.value = True
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This isn't your confirmation!", ephemeral=True)
            return
        self.value = False
        self.stop()


async def setup(bot):
    await bot.add_cog(Reminders(bot))
