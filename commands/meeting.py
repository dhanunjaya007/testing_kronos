import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
import logging
from typing import Optional, Literal

logger = logging.getLogger(__name__)

class Meetings(commands.Cog):
    def __init__(self, bot, get_db_connection_func):
        self.bot = bot
        self.get_db_connection = get_db_connection_func
        self.meetings = {}
        self.events = {}
        self.init_db_tables()

    def init_db_tables(self):
        """Initialize meetings and events tables"""
        try:
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        # Create meetings table
                        cur.execute("""
                            CREATE TABLE IF NOT EXISTS meetings (
                                id SERIAL PRIMARY KEY,
                                meeting_id TEXT NOT NULL UNIQUE,
                                title TEXT NOT NULL,
                                date DATE NOT NULL,
                                time TIME NOT NULL,
                                agenda TEXT,
                                notes TEXT,
                                creator_id BIGINT NOT NULL,
                                channel_id BIGINT,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                        """)
                        
                        # Create meeting_rsvp table with UNIQUE constraint
                        cur.execute("""
                            CREATE TABLE IF NOT EXISTS meeting_rsvp (
                                id SERIAL PRIMARY KEY,
                                meeting_id TEXT NOT NULL,
                                user_id BIGINT NOT NULL,
                                rsvp TEXT CHECK (rsvp IN ('yes','no','maybe')),
                                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                UNIQUE(meeting_id, user_id)
                            )
                        """)
                        
                        # Create events table
                        cur.execute("""
                            CREATE TABLE IF NOT EXISTS events (
                                id SERIAL PRIMARY KEY,
                                event_id TEXT NOT NULL UNIQUE,
                                title TEXT NOT NULL,
                                date DATE NOT NULL,
                                description TEXT,
                                creator_id BIGINT NOT NULL,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                        """)
                        conn.commit()
            logger.info("✅ Meetings/events tables initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize meetings/events tables: {e}")

    @commands.hybrid_group(name="meeting", description="Manage meetings", invoke_without_command=True)
    async def meeting(self, ctx: commands.Context):
        """Meeting commands help"""
        embed = discord.Embed(
            title="📅 Meeting Commands",
            description=(
                "**/meeting create <title> <date> <time> [agenda]** - Schedule a meeting\n"
                "**/meeting list [upcoming/past]** - View meetings\n"
                "**/meeting rsvp <meeting_id> <yes/no/maybe>** - RSVP to a meeting\n"
                "**/meeting cancel <meeting_id>** - Cancel your meeting\n"
                "**/meeting agenda <meeting_id> <agenda>** - Update agenda\n"
                "**/meeting notes <meeting_id> <notes>** - Add meeting notes"
            ),
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)

    @meeting.command(name="create", description="Schedule a team meeting")
    @app_commands.describe(
        title="Meeting title",
        date="Date (YYYY-MM-DD)",
        time="Time (HH:MM)",
        agenda="Meeting agenda (optional)"
    )
    async def meeting_create(self, ctx: commands.Context, title: str, date: str, time: str, agenda: Optional[str] = None):
        """Schedule a meeting"""
        try:
            meeting_dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
            if meeting_dt < datetime.utcnow():
                await ctx.send("❌ Cannot schedule meetings in the past!", ephemeral=True)
                return
                
            meeting_id = f"M{int(datetime.utcnow().timestamp())}"
            creator_id = ctx.author.id
            channel_id = ctx.channel.id
            
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO meetings (meeting_id, title, date, time, agenda, creator_id, channel_id)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (meeting_id, title, meeting_dt.date(), meeting_dt.time(), agenda, creator_id, channel_id))
                        conn.commit()
                        
            embed = discord.Embed(
                title="✅ Meeting Scheduled",
                description=f"**{title}**\n\n📅 {date} at {time}",
                color=discord.Color.green()
            )
            embed.add_field(name="Meeting ID", value=meeting_id, inline=False)
            if agenda:
                embed.add_field(name="Agenda", value=agenda, inline=False)
            embed.set_footer(text=f"Created by {ctx.author.display_name}")
            
            await ctx.send(embed=embed)
            
        except ValueError:
            await ctx.send("❌ Invalid date/time format. Use: `YYYY-MM-DD HH:MM` (e.g., 2024-12-25 14:30)", ephemeral=True)
        except Exception as e:
            logger.error(f"meeting_create failed: {e}")
            await ctx.send(f"❌ Failed to create meeting: {str(e)}", ephemeral=True)

    @meeting.command(name="list", description="View scheduled meetings")
    @app_commands.describe(filter="Filter by 'upcoming' or 'past'")
    async def meeting_list(self, ctx: commands.Context, filter: Optional[Literal["upcoming", "past"]] = None):
        """View meetings"""
        try:
            now = datetime.utcnow()
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        if filter == "past":
                            cur.execute(
                                "SELECT meeting_id, title, date, time FROM meetings WHERE date < %s ORDER BY date DESC, time DESC LIMIT 10",
                                (now.date(),)
                            )
                            title = "📜 Past Meetings"
                        else:
                            cur.execute(
                                "SELECT meeting_id, title, date, time FROM meetings WHERE date >= %s ORDER BY date ASC, time ASC LIMIT 10",
                                (now.date(),)
                            )
                            title = "📅 Upcoming Meetings"
                        rows = cur.fetchall()
                        
            if not rows:
                embed = discord.Embed(
                    title=title,
                    description="No meetings found.",
                    color=discord.Color.blue()
                )
                await ctx.send(embed=embed)
                return
                
            embed = discord.Embed(title=title, color=discord.Color.blue())
            for row in rows:
                embed.add_field(
                    name=f"📌 {row[1]}",
                    value=f"ID: `{row[0]}`\nDate: {row[2]} at {row[3]}",
                    inline=False
                )
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"meeting_list failed: {e}")
            await ctx.send("❌ Failed to fetch meetings.", ephemeral=True)

    @meeting.command(name="rsvp", description="Respond to meeting invitation")
    @app_commands.describe(
        meeting_id="Meeting ID to RSVP to",
        response="Your response (yes/no/maybe)"
    )
    async def meeting_rsvp(self, ctx: commands.Context, meeting_id: str, response: Literal["yes", "no", "maybe"]):
        """RSVP to a meeting"""
        try:
            user_id = ctx.author.id
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO meeting_rsvp (meeting_id, user_id, rsvp)
                            VALUES (%s, %s, %s)
                            ON CONFLICT (meeting_id, user_id) 
                            DO UPDATE SET rsvp = EXCLUDED.rsvp, updated_at = CURRENT_TIMESTAMP
                        """, (meeting_id, user_id, response))
                        conn.commit()
                        
            emoji_map = {"yes": "✅", "no": "❌", "maybe": "🤔"}
            await ctx.send(f"{emoji_map[response]} RSVP recorded: **{response}** for meeting `{meeting_id}`")
            
        except Exception as e:
            logger.error(f"meeting_rsvp failed: {e}")
            await ctx.send("❌ Failed to record RSVP.", ephemeral=True)

    @meeting.command(name="cancel", description="Cancel a scheduled meeting")
    @app_commands.describe(meeting_id="Meeting ID to cancel")
    async def meeting_cancel(self, ctx: commands.Context, meeting_id: str):
        """Cancel a meeting"""
        try:
            user_id = ctx.author.id
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT creator_id FROM meetings WHERE meeting_id = %s", (meeting_id,))
                        result = cur.fetchone()
                        
                        if not result:
                            await ctx.send("❌ Meeting not found!", ephemeral=True)
                            return
                            
                        if result[0] != user_id:
                            await ctx.send("❌ You can only cancel meetings you created!", ephemeral=True)
                            return
                            
                        cur.execute("DELETE FROM meetings WHERE meeting_id = %s", (meeting_id,))
                        conn.commit()
                        
            await ctx.send(f"✅ Meeting `{meeting_id}` has been cancelled.")
            
        except Exception as e:
            logger.error(f"meeting_cancel failed: {e}")
            await ctx.send("❌ Failed to cancel meeting.", ephemeral=True)

    @meeting.command(name="agenda", description="Add/update meeting agenda")
    @app_commands.describe(
        meeting_id="Meeting ID",
        agenda="Agenda items"
    )
    async def meeting_agenda(self, ctx: commands.Context, meeting_id: str, *, agenda: str):
        """Update meeting agenda"""
        try:
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("UPDATE meetings SET agenda = %s WHERE meeting_id = %s", (agenda, meeting_id))
                        conn.commit()
                        
            await ctx.send(f"✅ Agenda updated for meeting `{meeting_id}`")
            
        except Exception as e:
            logger.error(f"meeting_agenda failed: {e}")
            await ctx.send("❌ Failed to update agenda.", ephemeral=True)

    @meeting.command(name="notes", description="Add meeting notes/minutes")
    @app_commands.describe(
        meeting_id="Meeting ID",
        notes="Meeting notes"
    )
    async def meeting_notes(self, ctx: commands.Context, meeting_id: str, *, notes: str):
        """Add meeting notes"""
        try:
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("UPDATE meetings SET notes = %s WHERE meeting_id = %s", (notes, meeting_id))
                        conn.commit()
                        
            await ctx.send(f"✅ Notes updated for meeting `{meeting_id}`")
            
        except Exception as e:
            logger.error(f"meeting_notes failed: {e}")
            await ctx.send("❌ Failed to update notes.", ephemeral=True)

    @commands.hybrid_group(name="event", description="Manage events", invoke_without_command=True)
    async def event(self, ctx: commands.Context):
        """Event commands help"""
        embed = discord.Embed(
            title="🎉 Event Commands",
            description=(
                "**/event create <title> <date> <description>** - Create an event\n"
                "**/event list** - View all upcoming events"
            ),
            color=discord.Color.purple()
        )
        await ctx.send(embed=embed)

    @event.command(name="create", description="Create an event (hackathon, deadline, etc.)")
    @app_commands.describe(
        title="Event title",
        date="Date (YYYY-MM-DD)",
        description="Event description"
    )
    async def event_create(self, ctx: commands.Context, title: str, date: str, *, description: str):
        """Create an event"""
        try:
            event_dt = datetime.strptime(date, "%Y-%m-%d")
            if event_dt.date() < datetime.utcnow().date():
                await ctx.send("❌ Cannot create events in the past!", ephemeral=True)
                return
                
            event_id = f"E{int(datetime.utcnow().timestamp())}"
            creator_id = ctx.author.id
            
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO events (event_id, title, date, description, creator_id)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (event_id, title, event_dt.date(), description, creator_id))
                        conn.commit()
                        
            embed = discord.Embed(
                title="✅ Event Created",
                description=f"**{title}**\n\n📅 {date}\n\n{description}",
                color=discord.Color.gold()
            )
            embed.add_field(name="Event ID", value=event_id, inline=False)
            embed.set_footer(text=f"Created by {ctx.author.display_name}")
            
            await ctx.send(embed=embed)
            
        except ValueError:
            await ctx.send("❌ Invalid date format. Use: `YYYY-MM-DD`", ephemeral=True)
        except Exception as e:
            logger.error(f"event_create failed: {e}")
            await ctx.send(f"❌ Failed to create event: {str(e)}", ephemeral=True)

    @event.command(name="list", description="View all upcoming events")
    async def event_list(self, ctx: commands.Context):
        """View events"""
        try:
            now = datetime.utcnow()
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT event_id, title, date FROM events WHERE date >= %s ORDER BY date ASC LIMIT 10",
                            (now.date(),)
                        )
                        rows = cur.fetchall()
                        
            if not rows:
                embed = discord.Embed(
                    title="🎉 Upcoming Events",
                    description="No upcoming events.",
                    color=discord.Color.purple()
                )
                await ctx.send(embed=embed)
                return
                
            embed = discord.Embed(title="🎉 Upcoming Events", color=discord.Color.purple())
            for row in rows:
                embed.add_field(
                    name=f"📌 {row[1]}",
                    value=f"ID: `{row[0]}`\nDate: {row[2]}",
                    inline=False
                )
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"event_list failed: {e}")
            await ctx.send("❌ Failed to fetch events.", ephemeral=True)

async def setup(bot):
    """Setup function for the cog"""
    get_db_connection_func = getattr(bot, "get_db_connection", None)
    if not get_db_connection_func:
        logger.error("❌ get_db_connection not found on bot instance")
        return
    await bot.add_cog(Meetings(bot, get_db_connection_func))
    logger.info("✅ Meetings cog loaded")
