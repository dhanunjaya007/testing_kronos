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
        self.meetings = {}  # {meeting_id: meeting_data}
        self.events = {}    # {event_id: event_data}
        self.init_db_tables()

    def init_db_tables(self):
        try:
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
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
                        );
                        CREATE TABLE IF NOT EXISTS meeting_rsvp (
                            id SERIAL PRIMARY KEY,
                            meeting_id TEXT NOT NULL,
                            user_id BIGINT NOT NULL,
                            rsvp TEXT CHECK (rsvp IN ('yes','no','maybe')),
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );
                        CREATE TABLE IF NOT EXISTS events (
                            id SERIAL PRIMARY KEY,
                            event_id TEXT NOT NULL UNIQUE,
                            title TEXT NOT NULL,
                            date DATE NOT NULL,
                            description TEXT,
                            creator_id BIGINT NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );
                        """)
                        conn.commit()
            logger.info("Meetings/events tables initialized")
        except Exception as e:
            logger.error(f"Failed to initialize meetings/events tables: {e}")

    # /meeting create <title> <date> <time> [agenda]
    @app_commands.command(name="meeting_create", description="Schedule a team meeting")
    async def meeting_create(self, interaction: discord.Interaction, title: str, date: str, time: str, agenda: Optional[str] = None):
        try:
            # Validate date/time
            meeting_dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
            meeting_id = f"M{int(datetime.utcnow().timestamp())}"
            creator_id = interaction.user.id
            channel_id = interaction.channel.id if hasattr(interaction, "channel") else None
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                        INSERT INTO meetings (meeting_id, title, date, time, agenda, creator_id, channel_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (meeting_id, title, meeting_dt.date(), meeting_dt.time(), agenda, creator_id, channel_id))
                        conn.commit()
            embed = discord.Embed(title="Meeting Scheduled", description=f"Meeting **{title}** on **{date} {time}**", color=discord.Color.green())
            embed.add_field(name="Meeting ID", value=meeting_id)
            if agenda:
                embed.add_field(name="Agenda", value=agenda)
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            logger.error(f"meeting_create failed: {e}")
            await interaction.response.send_message("Failed to create meeting. Format: YYYY-MM-DD HH:MM", ephemeral=True)

    # /meeting list [upcoming/past]
    @app_commands.command(name="meeting_list", description="View scheduled meetings")
    async def meeting_list(self, interaction: discord.Interaction, filter: Optional[Literal["upcoming", "past"]] = None):
        try:
            now = datetime.utcnow()
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        if filter == "past":
                            cur.execute("SELECT meeting_id, title, date, time FROM meetings WHERE date < %s ORDER BY date DESC, time DESC;", (now.date(),))
                        else:
                            cur.execute("SELECT meeting_id, title, date, time FROM meetings WHERE date >= %s ORDER BY date ASC, time ASC;", (now.date(),))
                        rows = cur.fetchall()
            embed = discord.Embed(title="Meetings List", color=discord.Color.blue())
            for row in rows:
                embed.add_field(name=row[1], value=f"ID: {row[0]}, Date: {row[2]}, Time: {row[3]}", inline=False)
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            logger.error(f"meeting_list failed: {e}")
            await interaction.response.send_message("Failed to fetch meetings.", ephemeral=True)

    # /meeting rsvp <meeting_id> <yes/no/maybe>
    @app_commands.command(name="meeting_rsvp", description="Respond to meeting invitation")
    async def meeting_rsvp(self, interaction: discord.Interaction, meeting_id: str, response: Literal["yes", "no", "maybe"]):
        try:
            user_id = interaction.user.id
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        # Upsert RSVP
                        cur.execute("""
                        INSERT INTO meeting_rsvp (meeting_id, user_id, rsvp)
                        VALUES (%s, %s, %s) ON CONFLICT (meeting_id, user_id) DO UPDATE SET rsvp = EXCLUDED.rsvp, updated_at = CURRENT_TIMESTAMP
                        """, (meeting_id, user_id, response))
                        conn.commit()
            await interaction.response.send_message(f"RSVP '{response}' recorded for meeting {meeting_id}.")
        except Exception as e:
            logger.error(f"meeting_rsvp failed: {e}")
            await interaction.response.send_message("Failed to record RSVP.", ephemeral=True)

    # /meeting cancel <meeting_id>
    @app_commands.command(name="meeting_cancel", description="Cancel a scheduled meeting")
    async def meeting_cancel(self, interaction: discord.Interaction, meeting_id: str):
        try:
            # Only creator can cancel
            user_id = interaction.user.id
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT creator_id FROM meetings WHERE meeting_id = %s", (meeting_id,))
                        result = cur.fetchone()
                        if result and result[0] == user_id:
                            cur.execute("DELETE FROM meetings WHERE meeting_id = %s", (meeting_id,))
                            conn.commit()
                            await interaction.response.send_message(f"Meeting {meeting_id} cancelled.")
                        else:
                            await interaction.response.send_message("You can only cancel meetings you created!", ephemeral=True)
        except Exception as e:
            logger.error(f"meeting_cancel failed: {e}")
            await interaction.response.send_message("Failed to cancel meeting.", ephemeral=True)

    # /meeting reminder <meeting_id> <minutes_before>
    @app_commands.command(name="meeting_reminder", description="Set custom meeting reminder")
    async def meeting_reminder(self, interaction: discord.Interaction, meeting_id: str, minutes_before: int):
        await interaction.response.send_message("Custom meeting reminders feature not implemented in this quick template. Add logic to schedule reminder notification in your task loop.", ephemeral=True)

    # /meeting agenda <meeting_id> <agenda_items>
    @app_commands.command(name="meeting_agenda", description="Add/update meeting agenda")
    async def meeting_agenda(self, interaction: discord.Interaction, meeting_id: str, agenda_items: str):
        try:
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("UPDATE meetings SET agenda = %s WHERE meeting_id = %s", (agenda_items, meeting_id))
                        conn.commit()
            await interaction.response.send_message("Agenda updated.")
        except Exception as e:
            logger.error(f"meeting_agenda failed: {e}")
            await interaction.response.send_message("Failed to update agenda.", ephemeral=True)

    # /meeting notes <meeting_id> <notes>
    @app_commands.command(name="meeting_notes", description="Add meeting notes/minutes")
    async def meeting_notes(self, interaction: discord.Interaction, meeting_id: str, notes: str):
        try:
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("UPDATE meetings SET notes = %s WHERE meeting_id = %s", (notes, meeting_id))
                        conn.commit()
            await interaction.response.send_message("Notes updated.")
        except Exception as e:
            logger.error(f"meeting_notes failed: {e}")
            await interaction.response.send_message("Failed to update notes.", ephemeral=True)

    # /event create <title> <date> <description>
    @app_commands.command(name="event_create", description="Create an event (hackathon, deadline, etc.)")
    async def event_create(self, interaction: discord.Interaction, title: str, date: str, description: str):
        try:
            event_dt = datetime.strptime(date, "%Y-%m-%d")
            event_id = f"E{int(datetime.utcnow().timestamp())}"
            creator_id = interaction.user.id
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                        INSERT INTO events (event_id, title, date, description, creator_id)
                        VALUES (%s, %s, %s, %s, %s)
                        """, (event_id, title, event_dt.date(), description, creator_id))
                        conn.commit()
            embed = discord.Embed(title="Event Created", description=f"Event **{title}** on **{date}**", color=discord.Color.gold())
            embed.add_field(name="Event ID", value=event_id)
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            logger.error(f"event_create failed: {e}")
            await interaction.response.send_message("Failed to create event. Use YYYY-MM-DD format.", ephemeral=True)

    # /event list
    @app_commands.command(name="event_list", description="View all upcoming events")
    async def event_list(self, interaction: discord.Interaction):
        try:
            now = datetime.utcnow()
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT event_id, title, date FROM events WHERE date >= %s ORDER BY date ASC;", (now.date(),))
                        rows = cur.fetchall()
            embed = discord.Embed(title="Upcoming Events", color=discord.Color.purple())
            for row in rows:
                embed.add_field(name=row[1], value=f"ID: {row[0]}, Date: {row[2]}", inline=False)
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            logger.error(f"event_list failed: {e}")
            await interaction.response.send_message("Failed to fetch events.", ephemeral=True)

async def setup(bot):
    get_db_connection_func = getattr(bot, "get_db_connection", None)
    if not get_db_connection_func:
        logger.error("get_db_connection not found on bot instance")
        return
    await bot.add_cog(Meetings(bot, get_db_connection_func))
    logger.info("Meetings cog loaded")
