import secrets
from flask import Flask, request, jsonify
import threading
import discord
from discord import app_commands
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os
import requests
import asyncio
import psycopg2
from psycopg2 import pool
from contextlib import contextmanager
import time

# Import custom modules
from git_functions import setup_git_commands, register_github_routes
from ai_functions import setup_ai_commands

# Load environment variables
load_dotenv()
token = os.getenv('DISCORD_TOKEN')
DATABASE_URL = os.getenv('DATABASE_URL')

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger(__name__)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True  # REQUIRED for code editor tracking!

# Initialize bot with HYBRID commands
bot = commands.Bot(command_prefix='/', intents=intents)
app = Flask(__name__)

# Port configuration for deployment
port = int(os.environ.get("PORT", 10000))

# OpenRouter API Configuration
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY', '').strip()
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Available free models on OpenRouter
FREE_MODELS = {
    "llama": "meta-llama/llama-3.2-3b-instruct:free",
    "deepseek": "deepseek/deepseek-r1-distill-llama-70b:free",
    "gemini": "google/gemini-2.0-flash-exp:free",
    "mistral": "mistralai/mistral-7b-instruct:free"
}

DEFAULT_MODEL = "llama"
conversation_history = {}
webhook_data_memory = {}
bot_thread = None
DEPLOYMENT_URL = os.getenv('DEPLOYMENT_URL', 'https://testing-kronos.onrender.com')

# ============= DATABASE CONNECTION POOL =============
connection_pool = None

def init_all_database_tables():
    """Initialize ALL database tables automatically"""
    logger.info("🔧 Initializing database tables...")
    
    try:
        with get_db_connection() as conn:
            if not conn:
                logger.warning("⚠️ No database connection, skipping table creation")
                return False
                
            with conn.cursor() as cur:
                # Webhook data
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS webhook_data (
                        token VARCHAR(255) PRIMARY KEY,
                        guild_id BIGINT NOT NULL,
                        webhook_url TEXT NOT NULL,
                        webhook_id BIGINT NOT NULL,
                        webhook_token TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Coding sessions
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS coding_sessions (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT NOT NULL,
                        language TEXT NOT NULL,
                        editor TEXT,
                        file_name TEXT,
                        start_time TIMESTAMP NOT NULL,
                        end_time TIMESTAMP,
                        duration_minutes INT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Coding stats
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS coding_stats (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT NOT NULL,
                        language TEXT NOT NULL,
                        total_hours DECIMAL(10,2) DEFAULT 0,
                        session_count INT DEFAULT 0,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, language)
                    )
                """)
                
                # Reminders
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS reminders (
                        id SERIAL PRIMARY KEY,
                        reminder_id TEXT NOT NULL UNIQUE,
                        user_id BIGINT NOT NULL,
                        channel_id BIGINT NOT NULL,
                        target_user_id BIGINT,
                        message TEXT NOT NULL,
                        trigger_time TIMESTAMP NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        recurring BOOLEAN DEFAULT FALSE,
                        frequency TEXT,
                        next_trigger TIMESTAMP
                    )
                """)
                
                # Meetings
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
                
                # Meeting RSVP
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
                
                # Events
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
                
                # Team tasks
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS team_tasks (
                        id SERIAL PRIMARY KEY,
                        task_id TEXT NOT NULL UNIQUE,
                        title TEXT NOT NULL,
                        description TEXT,
                        assignee_id BIGINT,
                        creator_id BIGINT NOT NULL,
                        guild_id BIGINT NOT NULL,
                        deadline DATE,
                        priority TEXT CHECK (priority IN ('low', 'medium', 'high', 'urgent')),
                        status TEXT CHECK (status IN ('To Do', 'In Progress', 'Review', 'Done')),
                        dependency_task_id TEXT,
                        blocked BOOLEAN DEFAULT FALSE,
                        block_reason TEXT,
                        estimated_hours DECIMAL(5,2) DEFAULT 0,
                        time_logged DECIMAL(5,2) DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Personal tasks
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS personal_tasks (
                        id SERIAL PRIMARY KEY,
                        task_id TEXT NOT NULL UNIQUE,
                        user_id BIGINT NOT NULL,
                        title TEXT NOT NULL,
                        description TEXT,
                        deadline DATE,
                        status TEXT CHECK (status IN ('Pending', 'In Progress', 'Completed')),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Milestones
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS milestones (
                        id SERIAL PRIMARY KEY,
                        milestone_id TEXT NOT NULL UNIQUE,
                        title TEXT NOT NULL,
                        description TEXT,
                        deadline DATE,
                        status TEXT CHECK (status IN ('Active', 'Completed', 'Cancelled')),
                        progress INTEGER DEFAULT 0 CHECK (progress >= 0 AND progress <= 100),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Celebrations
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
                
                # Shoutouts
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
                
                # Morale stats
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
                
                # Focus sessions
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
                
                # Pomodoro sessions
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
                
                # DND status
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
                
                # Productivity stats
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
                
                # Report schedules
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS report_schedules (
                        id SERIAL PRIMARY KEY,
                        guild_id BIGINT NOT NULL,
                        channel_id BIGINT NOT NULL,
                        frequency TEXT CHECK (frequency IN ('daily', 'weekly')) NOT NULL,
                        last_sent TIMESTAMP,
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(guild_id, channel_id, frequency)
                    )
                """)
                
                # Blockers
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS blockers (
                        id SERIAL PRIMARY KEY,
                        blocker_id TEXT NOT NULL UNIQUE,
                        description TEXT NOT NULL,
                        resolved BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # User XP levels
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS user_xp_levels (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT NOT NULL,
                        guild_id BIGINT NOT NULL,
                        xp INT DEFAULT 0,
                        level INT DEFAULT 1,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, guild_id)
                    )
                """)
                
                # User badges
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS user_badges (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT NOT NULL,
                        guild_id BIGINT NOT NULL,
                        badge_name TEXT NOT NULL,
                        date_earned TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Challenges
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS challenges (
                        id SERIAL PRIMARY KEY,
                        challenge_id TEXT NOT NULL UNIQUE,
                        title TEXT NOT NULL,
                        description TEXT,
                        xp_reward INT DEFAULT 0,
                        guild_id BIGINT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Completed challenges
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS completed_challenges (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT NOT NULL,
                        challenge_id TEXT NOT NULL,
                        guild_id BIGINT NOT NULL,
                        completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, challenge_id, guild_id)
                    )
                """)
                
                # User streaks
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS user_streaks (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT NOT NULL,
                        guild_id BIGINT NOT NULL,
                        current_streak INT DEFAULT 0,
                        longest_streak INT DEFAULT 0,
                        last_activity TIMESTAMP,
                        UNIQUE(user_id, guild_id)
                    )
                """)
                
                # User kudos
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS user_kudos (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT NOT NULL,
                        guild_id BIGINT NOT NULL,
                        kudos INT DEFAULT 0,
                        UNIQUE(user_id, guild_id)
                    )
                """)
                
                # Standup responses
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
                
                # User status
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
                logger.info("✅ All database tables initialized successfully!")
                return True
                
    except Exception as e:
        logger.error(f"❌ Failed to initialize database tables: {e}")
        import traceback
        traceback.print_exc()
        return False

def init_db_pool():
    """Initialize PostgreSQL connection pool"""
    global connection_pool
    if not DATABASE_URL:
        logger.warning("DATABASE_URL not set. Using in-memory storage only.")
        return None
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            connection_pool = psycopg2.pool.SimpleConnectionPool(
                1, 10,
                DATABASE_URL,
                sslmode='require',
                connect_timeout=30
            )
            
            logger.info("✅ PostgreSQL connection pool initialized")
            
            # Automatically initialize all tables
            init_all_database_tables()
            
            return connection_pool
        except Exception as e:
            logger.error(f"❌ Failed to initialize database pool (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
            else:
                logger.warning("⚠️ Falling back to in-memory storage")
                return None

@contextmanager
def get_db_connection():
    """Context manager for database connections"""
    conn = None
    try:
        if connection_pool:
            conn = connection_pool.getconn()
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            yield conn
        else:
            yield None
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        if conn:
            try:
                conn.rollback()
            except:
                pass
            try:
                connection_pool.putconn(conn, close=True)
            except:
                pass
        yield None
    finally:
        if conn and connection_pool:
            try:
                connection_pool.putconn(conn)
            except:
                pass

# ============= TOKEN MANAGEMENT =============
def save_webhook_data(token, guild_id, webhook_url, webhook_id, webhook_token):
    """Save webhook data"""
    webhook_data_memory[token] = {
        'guild_id': guild_id,
        'webhook_url': webhook_url,
        'webhook_id': webhook_id,
        'webhook_token': webhook_token
    }
    
    try:
        with get_db_connection() as conn:
            if conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO webhook_data (token, guild_id, webhook_url, webhook_id, webhook_token) 
                           VALUES (%s, %s, %s, %s, %s) 
                           ON CONFLICT (token) DO UPDATE 
                           SET guild_id = %s, webhook_url = %s, webhook_id = %s, webhook_token = %s""",
                        (token, guild_id, webhook_url, webhook_id, webhook_token,
                         guild_id, webhook_url, webhook_id, webhook_token)
                    )
                    conn.commit()
                    logger.info(f"✅ Saved webhook data for guild {guild_id}")
    except Exception as e:
        logger.error(f"❌ PostgreSQL save failed: {e}")

def get_webhook_data(token):
    """Get webhook data from token"""
    if token in webhook_data_memory:
        return webhook_data_memory[token]
    
    try:
        with get_db_connection() as conn:
            if conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT guild_id, webhook_url, webhook_id, webhook_token FROM webhook_data WHERE token = %s", 
                        (token,)
                    )
                    result = cur.fetchone()
                    if result:
                        data = {
                            'guild_id': result[0],
                            'webhook_url': result[1],
                            'webhook_id': result[2],
                            'webhook_token': result[3]
                        }
                        webhook_data_memory[token] = data
                        return data
    except Exception as e:
        logger.error(f"❌ PostgreSQL lookup failed: {e}")
    
    return None

def load_webhook_data_from_db():
    """Load webhook data from database"""
    try:
        with get_db_connection() as conn:
            if conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT token, guild_id, webhook_url, webhook_id, webhook_token FROM webhook_data")
                    results = cur.fetchall()
                    for token, guild_id, webhook_url, webhook_id, webhook_token in results:
                        webhook_data_memory[token] = {
                            'guild_id': guild_id,
                            'webhook_url': webhook_url,
                            'webhook_id': webhook_id,
                            'webhook_token': webhook_token
                        }
                    logger.info(f"✅ Loaded {len(results)} webhook entries")
                    return True
    except Exception as e:
        logger.error(f"❌ Failed to load webhook data: {e}")
    return False

# Register GitHub routes
register_github_routes(app, bot, get_webhook_data, load_webhook_data_from_db, DEPLOYMENT_URL)

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'bot_ready': bot.is_ready(),
        'guilds': len(bot.guilds) if bot.is_ready() else 0,
        'webhooks': len(webhook_data_memory)
    }), 200

@app.route('/', methods=['GET'])
def home():
    """Home route"""
    return jsonify({
        'bot': 'Discord Bot',
        'status': 'running',
        'bot_online': bot.is_ready()
    }), 200

bot.get_db_connection = get_db_connection

# ============= BOT EVENTS =============

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user.name}")
    print(f"Connected to {len(bot.guilds)} guilds")
    
    # Load webhook data
    load_webhook_data_from_db()
    
    # Setup commands
    setup_git_commands(bot, save_webhook_data, DEPLOYMENT_URL)
    setup_ai_commands(bot, OPENROUTER_API_KEY, OPENROUTER_URL, FREE_MODELS, DEFAULT_MODEL)
    
    # List of cogs to load
    cogs = [
        "commands.moderation",
        "commands.code_editor",
        "commands.reminders",
        "commands.meeting",
        "commands.task_milestone",
        "commands.celebration",
        "commands.productivity",
        "commands.report",
        "commands.timetracking",
        "commands.progress_tracking",
        "commands.gamification_XPsystem",
        "commands.collaboration_notification"
    ]
    
    # Load each cog with error handling
    for cog in cogs:
        try:
            await bot.load_extension(cog)
            print(f"✅ Loaded {cog}")
        except Exception as e:
            print(f"⚠️ Failed to load {cog}: {e}")
            import traceback
            traceback.print_exc()
    
    # Sync commands
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} commands")
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")
    
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.listening,
            name="/help | AI + GitHub"
        )
    )

@bot.event
async def on_guild_join(guild):
    """When bot joins a server"""
    print(f"🎉 Joined guild: {guild.name}")
    try:
        await bot.tree.sync(guild=guild)
    except Exception as e:
        print(f"⚠️ Failed to sync for {guild.name}: {e}")

@bot.event
async def on_message(message):
    """Handle messages"""
    if message.author == bot.user:
        return
    await bot.process_commands(message)

# ============= BASIC COMMANDS =============

@bot.hybrid_command(name="hello", description="Say hello")
async def hello(ctx: commands.Context):
    """Say hello"""
    await ctx.send(f"👋 Hello {ctx.author.mention}!")

@bot.hybrid_command(name="ping", description="Check bot latency")
async def ping(ctx: commands.Context):
    """Check latency"""
    latency = round(bot.latency * 1000)
    embed = discord.Embed(title="🏓 Pong!", color=discord.Color.green())
    embed.add_field(name="Latency", value=f"{latency}ms")
    await ctx.send(embed=embed)

@bot.hybrid_command(name="serverinfo", description="Get server information")
async def serverinfo(ctx: commands.Context):
    """Server information"""
    guild = ctx.guild
    embed = discord.Embed(title=f"📊 {guild.name}", color=discord.Color.blue())
    embed.add_field(name="Owner", value=guild.owner.mention)
    embed.add_field(name="Members", value=guild.member_count)
    embed.add_field(name="Roles", value=len(guild.roles))
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    await ctx.send(embed=embed)

# ERROR HANDLERS
@bot.event
async def on_command_error(ctx, error):
    """Handle errors"""
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ No permission", ephemeral=True)
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing: `{error.param.name}`", ephemeral=True)
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        await ctx.send(f"❌ Error: {str(error)}", ephemeral=True)
        logger.error(f"Command error: {error}", exc_info=True)

# ============= STARTUP =============

def start_bot():
    """Start the bot"""
    global bot_thread
    if not token:
        print("❌ DISCORD_TOKEN not found!")
        return
    
    # Initialize database
    init_db_pool()
    
    # Pre-load webhook data
    print("📦 Pre-loading webhook data...")
    if load_webhook_data_from_db():
        print(f"✅ {len(webhook_data_memory)} webhooks loaded")
    
    def run_bot():
        try:
            print("🤖 Starting bot...")
            bot.run(token, log_handler=handler, log_level=logging.INFO)
        except Exception as e:
            logger.error(f"Bot failed: {e}")
    
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    print("✅ Bot thread started")

# Start bot
if __name__ == "__main__":
    start_bot()
    print("🌐 Starting Flask...")
    app.run(host="0.0.0.0", port=port, debug=False)
else:
    start_bot()

