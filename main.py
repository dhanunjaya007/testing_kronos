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

# Initialize bot with HYBRID commands (supports both / prefix and slash commands)
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

# Default model
DEFAULT_MODEL = "llama"

# Store conversation history
conversation_history = {}

# Store webhook information: token -> {'guild_id': id, 'webhook_url': url, 'webhook_id': id, 'webhook_token': token}
webhook_data_memory = {}

# Bot running flag
bot_thread = None

# Deployment URL
DEPLOYMENT_URL = os.getenv('DEPLOYMENT_URL', 'https://testing-kronos.onrender.com')

# ============= DATABASE CONNECTION POOL =============
connection_pool = None

def init_db_pool():
    """Initialize PostgreSQL connection pool with proper SSL settings"""
    global connection_pool
    if not DATABASE_URL:
        logger.warning("DATABASE_URL not set. Using in-memory storage only.")
        return None
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # Parse DATABASE_URL and fix SSL settings
            db_url = DATABASE_URL
            # Render.com PostgreSQL requires SSL
            connection_pool = psycopg2.pool.SimpleConnectionPool(
                1, 10,  # min and max connections
                db_url,
                sslmode='require',
                connect_timeout=30
            )
            
            logger.info("✅ PostgreSQL connection pool initialized")
            
            # Initialize database table with webhook URL storage
            with get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
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
                        conn.commit()
                        logger.info("✅ Database table initialized")
            
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
    """Context manager for database connections with retry logic"""
    conn = None
    try:
        if connection_pool:
            conn = connection_pool.getconn()
            # Test connection before using
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
        
        # Try to reconnect once
        try:
            if connection_pool:
                conn = connection_pool.getconn()
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                yield conn
                return
        except:
            pass
        
        yield None
    finally:
        if conn and connection_pool:
            try:
                connection_pool.putconn(conn)
            except:
                pass

# ============= TOKEN MANAGEMENT WITH DB =============
def save_webhook_data(token, guild_id, webhook_url, webhook_id, webhook_token):
    """Save webhook data to both database and memory"""
    # Always save to memory first
    webhook_data_memory[token] = {
        'guild_id': guild_id,
        'webhook_url': webhook_url,
        'webhook_id': webhook_id,
        'webhook_token': webhook_token
    }
    
    # Try to save to database
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
                    logger.info(f"✅ Saved webhook data for guild {guild_id} to PostgreSQL")
            else:
                logger.warning("Database unavailable, using memory storage only")
    except Exception as e:
        logger.error(f"❌ PostgreSQL save failed: {e}")
        logger.info("✅ Webhook data saved to memory as fallback")

def get_webhook_data(token):
    """Get webhook data from token (checks memory first, then DB)"""
    # Check memory first (fastest and most reliable)
    if token in webhook_data_memory:
        logger.info(f"✅ Token found in memory cache")
        return webhook_data_memory[token]
    
    # Check database with retry
    logger.info(f"Token not in cache, checking database...")
    for attempt in range(2):  # Try twice
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
                            # Cache in memory for future requests
                            webhook_data_memory[token] = data
                            logger.info(f"✅ Token found in database, cached to memory")
                            return data
                        else:
                            logger.warning(f"Token not found in database")
                            return None
                else:
                    logger.warning(f"Database connection unavailable (attempt {attempt + 1}/2)")
                    if attempt == 0:
                        continue
        except Exception as e:
            logger.error(f"❌ PostgreSQL lookup failed (attempt {attempt + 1}/2): {e}")
            if attempt == 0:
                time.sleep(0.5)  # Brief pause before retry
                continue
    
    logger.error(f"❌ Failed to retrieve token after all attempts")
    return None

def load_webhook_data_from_db():
    """Load all webhook data from database into memory on startup"""
    max_retries = 3
    for attempt in range(max_retries):
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
                        logger.info(f"✅ Loaded {len(results)} webhook entries from database to memory")
                        return True
                else:
                    logger.warning(f"Database unavailable (attempt {attempt + 1}/{max_retries})")
        except Exception as e:
            logger.error(f"❌ Failed to load webhook data (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(1)
    
    logger.error("❌ Could not load webhook data from database after all retries")
    return False

# FIXED: Register GitHub webhook routes with correct parameters
register_github_routes(app, bot, get_webhook_data, load_webhook_data_from_db, DEPLOYMENT_URL)

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    db_status = "connected" if connection_pool else "disconnected"
    webhooks_status = "loaded" if webhook_data_memory else "empty"
    
    valid_guild_ids = {guild.id for guild in bot.guilds} if bot.is_ready() else set()
    valid_webhooks = sum(1 for data in webhook_data_memory.values() if data['guild_id'] in valid_guild_ids)
    invalid_webhooks = len(webhook_data_memory) - valid_webhooks
    
    guild_info = [{'id': g.id, 'name': g.name, 'member_count': g.member_count} for g in bot.guilds] if bot.is_ready() else []
    
    return jsonify({
        'status': 'ok',
        'bot_ready': bot.is_ready(),
        'bot_latency': round(bot.latency * 1000) if bot.is_ready() else None,
        'guilds': len(bot.guilds) if bot.is_ready() else 0,
        'guild_details': guild_info,
        'registered_webhooks': len(webhook_data_memory),
        'valid_webhooks': valid_webhooks,
        'invalid_webhooks': invalid_webhooks,
        'webhooks_status': webhooks_status,
        'database': db_status
    }), 200

@app.route('/', methods=['GET'])
def home():
    """Home route"""
    return jsonify({
        'bot': 'Discord Bot with AI and GitHub Integration',
        'status': 'running',
        'bot_online': bot.is_ready(),
        'endpoints': ['/health', '/github/<token>'],
        'setup_guide': 'Use /setupgit slash command in Discord'
    }), 200

# ============= BOT EVENTS =============

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user.name} (ID: {bot.user.id})")
    print(f"Connected to {len(bot.guilds)} guild(s):")
    
    for guild in bot.guilds:
        print(f"  - {guild.name} (ID: {guild.id}) | Members: {guild.member_count}")
    
    print(f"🤖 Using OpenRouter with model: {DEFAULT_MODEL}")
    if not OPENROUTER_API_KEY:
        print("⚠️ WARNING: OPENROUTER_API_KEY not set!")
    
    print("🔄 Refreshing webhook cache...")
    success = load_webhook_data_from_db()
    if success:
        print(f"✅ {len(webhook_data_memory)} webhook entries loaded and ready")
    else:
        print("⚠️ Using memory-only storage")
    
    # Load moderation cog
    try:
        await bot.load_extension("commands.moderation")
        print("✅ Moderation commands loaded")
    except Exception as e:
        print(f"⚠️ Moderation cog error: {e}")
    
    # FIXED: Setup custom commands BEFORE syncing
    setup_git_commands(bot, save_webhook_data, DEPLOYMENT_URL)
    setup_ai_commands(bot, OPENROUTER_API_KEY, OPENROUTER_URL, FREE_MODELS, DEFAULT_MODEL)
    
    # Sync slash commands with Discord
    print("🔄 Syncing slash commands with Discord...")
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash command(s) globally")
        print(f"📋 Commands: {[cmd.name for cmd in synced]}")
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")
        import traceback
        traceback.print_exc()
    
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.listening,
            name="/help | AI + GitHub"
        )
    )

@bot.event
async def on_guild_join(guild):
    """When bot joins a new server"""
    print(f"🎉 Joined guild: {guild.name} (ID: {guild.id})")
    
    # Sync slash commands for this guild
    try:
        await bot.tree.sync(guild=guild)
        print(f"✅ Synced slash commands for guild {guild.name}")
    except Exception as e:
        print(f"⚠️ Failed to sync commands for {guild.name}: {e}")
    
    if guild.system_channel and guild.system_channel.permissions_for(guild.me).send_messages:
        embed = discord.Embed(
            title="👋 Thanks for adding me!",
            description=(
                "**Quick Setup:**\n"
                "1. Create a `git` channel\n"
                "2. Use `/setupgit` for webhook URL\n"
                "3. Add to GitHub repo settings\n\n"
                "**Commands:** `/help`, `/chat`, `/models`"
            ),
            color=discord.Color.green()
        )
        await guild.system_channel.send(embed=embed)

@bot.event
async def on_member_join(member):
    """Welcome new members"""
    try:
        await member.send(f"👋 Welcome to **{member.guild.name}**!\nType `/help` for commands.")
        if member.guild.system_channel:
            await member.guild.system_channel.send(f"👋 Welcome {member.mention}!")
    except discord.Forbidden:
        pass

@bot.event
async def on_message(message):
    """Handle messages"""
    if message.author == bot.user:
        return
    
    content_lower = message.content.lower()
    
    if "fuckyou" in content_lower.replace(" ", ""):
        try:
            await message.delete()
            await message.channel.send(f"{message.author.mention} Please be friendly! 😊", delete_after=5)
        except discord.Forbidden:
            pass
    
    if "love you" in content_lower and not message.content.startswith('/'):
        await message.channel.send(f"{message.author.mention} Love you too! ❤️")
    
    await bot.process_commands(message)

# ============= SLASH COMMANDS =============

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
    
    # Pre-load webhook data into memory BEFORE starting bot
    print("📦 Pre-loading webhook data from database...")
    if load_webhook_data_from_db():
        print(f"✅ {len(webhook_data_memory)} webhook entries loaded and ready")
    else:
        print("⚠️ Using memory-only storage")
    
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
start_bot()

if __name__ == "__main__":
    print("🌐 Starting Flask...")
    app.run(host="0.0.0.0", port=port, debug=False)
