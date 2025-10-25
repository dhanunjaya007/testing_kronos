import secrets
from flask import Flask, request, jsonify
import threading
import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os
import requests
import asyncio
import psycopg2
from psycopg2 import pool
from contextlib import contextmanager

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

# Initialize bot and Flask app
bot = commands.Bot(command_prefix='!', intents=intents)
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

# In-memory backup for tokens (fallback if DB fails)
webhook_tokens_memory = {}

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
    
    try:
        # Parse DATABASE_URL and fix SSL settings
        db_url = DATABASE_URL
        
        # Render.com PostgreSQL requires SSL
        connection_pool = psycopg2.pool.SimpleConnectionPool(
            1, 10,  # min and max connections
            db_url,
            sslmode='require',  # Changed from default
            connect_timeout=10
        )
        
        logger.info("✅ PostgreSQL connection pool initialized")
        
        # Initialize database table
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS webhook_tokens (
                        token VARCHAR(255) PRIMARY KEY,
                        guild_id BIGINT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.commit()
                logger.info("✅ Database table initialized")
        
        return connection_pool
    except Exception as e:
        logger.error(f"❌ Failed to initialize database pool: {e}")
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

def save_webhook_token(token, guild_id):
    """Save webhook token to both database and memory"""
    # Always save to memory first
    webhook_tokens_memory[token] = guild_id
    
    # Try to save to database
    try:
        with get_db_connection() as conn:
            if conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO webhook_tokens (token, guild_id) VALUES (%s, %s) ON CONFLICT (token) DO UPDATE SET guild_id = %s",
                        (token, guild_id, guild_id)
                    )
                    conn.commit()
                    logger.info(f"✅ Saved token for guild {guild_id} to PostgreSQL")
            else:
                logger.warning("Database unavailable, using memory storage only")
    except Exception as e:
        logger.error(f"❌ PostgreSQL save failed: {e}")
        logger.info("✅ Token saved to memory as fallback")

def get_guild_from_token(token):
    """Get guild ID from webhook token (checks memory first, then DB)"""
    # Check memory first (fastest and most reliable)
    if token in webhook_tokens_memory:
        logger.info(f"✅ Token found in memory cache")
        return webhook_tokens_memory[token]
    
    # Check database with retry
    logger.info(f"Token not in cache, checking database...")
    for attempt in range(2):  # Try twice
        try:
            with get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT guild_id FROM webhook_tokens WHERE token = %s", (token,))
                        result = cur.fetchone()
                        if result:
                            guild_id = result[0]
                            # Cache in memory for future requests
                            webhook_tokens_memory[token] = guild_id
                            logger.info(f"✅ Token found in database, cached to memory")
                            return guild_id
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
                import time
                time.sleep(0.5)  # Brief pause before retry
                continue
    
    logger.error(f"❌ Failed to retrieve token after all attempts")
    return None

def load_tokens_from_db():
    """Load all tokens from database into memory on startup"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            with get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT token, guild_id FROM webhook_tokens")
                        results = cur.fetchall()
                        for token, guild_id in results:
                            webhook_tokens_memory[token] = guild_id
                        logger.info(f"✅ Loaded {len(results)} tokens from database to memory")
                        return True
                else:
                    logger.warning(f"Database unavailable (attempt {attempt + 1}/{max_retries})")
        except Exception as e:
            logger.error(f"❌ Failed to load tokens (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                import time
                time.sleep(1)
    
    logger.error("❌ Could not load tokens from database after all retries")
    return False

# ============= GIT FUNCTIONS =============

async def find_git_channel(guild):
    """Find a channel named 'git' in the given guild"""
    for channel in guild.text_channels:
        if channel.name.lower() == 'git':
            return channel
    
    for channel in guild.text_channels:
        if 'git' in channel.name.lower():
            return channel
    return None

def generate_webhook_token(guild_id):
    """Generate a unique webhook token for a guild"""
    token = secrets.token_urlsafe(32)
    save_webhook_token(token, guild_id)
    logger.info(f"✅ Generated new token for guild {guild_id}")
    return token

# ============= FLASK ROUTES =============

@app.before_first_request
def ensure_tokens_loaded():
    """Ensure tokens are loaded before handling any request"""
    if not webhook_tokens_memory:
        logger.info("🔄 First request - ensuring tokens are loaded...")
        load_tokens_from_db()
        logger.info(f"✅ Ready with {len(webhook_tokens_memory)} tokens")

@app.route('/github/<token>', methods=['POST'])
def github_webhook(token):
    """Handle GitHub webhook for commit notifications"""
    try:
        # Log incoming request
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        logger.info(f"Webhook request from {client_ip} with token: {token[:10]}...")
        
        # Ensure tokens are loaded (lazy load if not already done)
        if not webhook_tokens_memory:
            logger.info("Memory cache empty, loading from database...")
            load_tokens_from_db()
        
        data = request.json
        if not data:
            return jsonify({'error': 'No JSON data received'}), 400
        
        # Log event type
        event_type = request.headers.get('X-GitHub-Event', 'unknown')
        repo_name = data.get('repository', {}).get('name', 'Unknown')
        logger.info(f"GitHub event: {event_type} from repo: {repo_name}")
        
        # Get guild ID from token
        guild_id = get_guild_from_token(token)
        if not guild_id:
            logger.warning(f"Invalid webhook token: {token[:10]}... from IP: {client_ip}, repo: {repo_name}")
            logger.info(f"Current memory cache has {len(webhook_tokens_memory)} tokens")
            return jsonify({'error': 'Invalid webhook token'}), 403
        
        # Get the guild
        guild = bot.get_guild(guild_id)
        if not guild:
            logger.error(f"Guild {guild_id} not found")
            return jsonify({'error': 'Guild not found'}), 404
        
        # Handle ping event
        if event_type == 'ping':
            logger.info(f"✅ GitHub ping successful for guild {guild.name}")
            return jsonify({
                'status': 'success',
                'message': 'Webhook configured successfully!',
                'guild': guild.name
            }), 200
        
        # Create async task
        async def send_github_notification():
            git_channel = await find_git_channel(guild)
            
            if not git_channel:
                logger.warning(f"No 'git' channel in guild {guild.name}")
                return False
            
            if not git_channel.permissions_for(guild.me).send_messages:
                logger.error(f"No permission in {git_channel.name}")
                return False
            
            commits = data.get('commits', [])
            repository = data.get('repository', {})
            repo_name = repository.get('name', 'Unknown Repository')
            repo_url = repository.get('html_url', '')
            pusher = data.get('pusher', {}).get('name', 'Unknown')
            ref = data.get('ref', '').split('/')[-1]
            
            if commits:
                embeds = []
                total_commits = len(commits)
                
                for i in range(0, total_commits, 5):
                    batch_start = i + 1
                    batch_end = min(i + 5, total_commits)
                    
                    embed = discord.Embed(
                        title=f"🔔 New Push to {repo_name}",
                        url=repo_url,
                        color=discord.Color.blue(),
                        description=f"**Commits {batch_start}-{batch_end}** of **{total_commits}** pushed to `{ref}` by **{pusher}**"
                    )
                    
                    for commit in commits[i:i+5]:
                        author = commit.get('author', {}).get('name', 'Unknown')
                        message = commit.get('message', 'No message')
                        commit_url = commit.get('url', '')
                        commit_id = commit.get('id', '')[:7]
                        
                        if len(message) > 100:
                            message = message[:97] + "..."
                        
                        embed.add_field(
                            name=f"`{commit_id}` - {author}",
                            value=f"[{message}]({commit_url})",
                            inline=False
                        )
                    
                    embeds.append(embed)
                
                for embed in embeds[:10]:
                    await git_channel.send(embed=embed)
                
                if total_commits > 50:
                    await git_channel.send(
                        f"⚠️ **{total_commits - 50}** more commits not shown. View at {repo_url}"
                    )
            else:
                await git_channel.send(
                    f"🔔 GitHub event (`{event_type}`) from **{repo_name}** by **{pusher}**"
                )
            
            logger.info(f"✅ Notification sent to {guild.name}")
            return True
        
        if bot.is_ready():
            future = asyncio.run_coroutine_threadsafe(send_github_notification(), bot.loop)
            result = future.result(timeout=10)
            
            if result:
                return jsonify({'status': 'success', 'guild': guild.name}), 200
            else:
                return jsonify({'error': 'Failed to send notification'}), 500
        else:
            return jsonify({'error': 'Bot not ready'}), 503
    
    except Exception as e:
        logger.error(f"GitHub webhook error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    db_status = "connected" if connection_pool else "disconnected"
    
    # Check if tokens are loaded
    tokens_status = "loaded" if webhook_tokens_memory else "empty"
    
    return jsonify({
        'status': 'ok',
        'bot_ready': bot.is_ready(),
        'bot_latency': round(bot.latency * 1000) if bot.is_ready() else None,
        'guilds': len(bot.guilds) if bot.is_ready() else 0,
        'registered_webhooks': len(webhook_tokens_memory),
        'tokens_status': tokens_status,
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
        'setup_guide': 'Use !setupgit command in Discord'
    }), 200

# ============= BOT EVENTS =============

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user.name} (ID: {bot.user.id})")
    print(f"Connected to {len(bot.guilds)} guild(s)")
    print(f"🤖 Using OpenRouter with model: {DEFAULT_MODEL}")
    
    if not OPENROUTER_API_KEY:
        print("⚠️ WARNING: OPENROUTER_API_KEY not set!")
    
    # Reload tokens to ensure we have latest (in case of bot restart)
    print("🔄 Refreshing token cache...")
    success = load_tokens_from_db()
    if success:
        print(f"✅ {len(webhook_tokens_memory)} tokens in cache")
    
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.listening,
            name="!help | AI + GitHub"
        )
    )

@bot.event
async def on_guild_join(guild):
    """When bot joins a new server"""
    print(f"🎉 Joined guild: {guild.name} (ID: {guild.id})")
    
    if guild.system_channel and guild.system_channel.permissions_for(guild.me).send_messages:
        embed = discord.Embed(
            title="👋 Thanks for adding me!",
            description=(
                "**Quick Setup:**\n"
                "1. Create a `git` channel\n"
                "2. Use `!setupgit` for webhook URL\n"
                "3. Add to GitHub repo settings\n\n"
                "**Commands:** `!help`, `!chat`, `!models`"
            ),
            color=discord.Color.green()
        )
        await guild.system_channel.send(embed=embed)

@bot.event
async def on_member_join(member):
    """Welcome new members"""
    try:
        await member.send(
            f"👋 Welcome to **{member.guild.name}**!\nType `!help` for commands."
        )
        
        if member.guild.system_channel:
            await member.guild.system_channel.send(
                f"👋 Welcome {member.mention}!"
            )
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
            await message.channel.send(
                f"{message.author.mention} Please be friendly! 😊",
                delete_after=5
            )
        except discord.Forbidden:
            pass
    
    if "love you" in content_lower and not message.content.startswith('!'):
        await message.channel.send(f"{message.author.mention} Love you too! ❤️")
    
    await bot.process_commands(message)

# ============= GITHUB COMMANDS =============

@bot.command()
@commands.has_permissions(administrator=True)
async def setupgit(ctx):
    """Set up GitHub webhook (Admin only)"""
    guild = ctx.guild
    git_channel = await find_git_channel(guild)
    
    if not git_channel:
        embed = discord.Embed(
            title="❌ No 'git' Channel",
            description="Create a channel named `git` first!\nUse `!creategit`",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return
    
    token = generate_webhook_token(guild.id)
    webhook_url = f"{DEPLOYMENT_URL}/github/{token}"
    
    embed = discord.Embed(
        title="✅ GitHub Webhook Setup",
        description=f"Commits will post in {git_channel.mention}",
        color=discord.Color.green()
    )
    
    embed.add_field(
        name="📋 Webhook URL",
        value=f"```{webhook_url}```",
        inline=False
    )
    
    embed.add_field(
        name="🔧 GitHub Setup",
        value=(
            "1. Go to repo **Settings** → **Webhooks**\n"
            "2. Click **Add webhook**\n"
            "3. Paste URL above\n"
            "4. Content type: `application/json`\n"
            "5. Select **Just push event**\n"
            "6. Click **Add webhook**"
        ),
        inline=False
    )
    
    embed.set_footer(text="⚠️ Keep this URL private!")
    
    try:
        await ctx.author.send(embed=embed)
        await ctx.send("✅ Sent to your DMs! 📬", delete_after=10)
        try:
            await ctx.message.delete()
        except:
            pass
    except discord.Forbidden:
        await ctx.send(
            "⚠️ Couldn't DM you! Delete after copying:",
            embed=embed,
            delete_after=60
        )

@bot.command()
@commands.has_permissions(administrator=True)
async def creategit(ctx):
    """Create a 'git' channel (Admin only)"""
    guild = ctx.guild
    git_channel = await find_git_channel(guild)
    
    if git_channel:
        await ctx.send(f"ℹ️ Git channel exists: {git_channel.mention}")
        return
    
    try:
        new_channel = await guild.create_text_channel(
            name='git',
            topic='📦 GitHub notifications',
            reason=f'Created by {ctx.author}'
        )
        
        embed = discord.Embed(
            title="✅ Git Channel Created!",
            description=f"{new_channel.mention} ready for GitHub!\nUse `!setupgit` next.",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
        
        await new_channel.send("🎉 Git channel ready! Use `!setupgit` to connect GitHub.")
    except discord.Forbidden:
        await ctx.send("❌ No permission to create channels.")
    except Exception as e:
        await ctx.send(f"❌ Error: {e}")

@bot.command()
async def testgit(ctx):
    """Test git channel"""
    git_channel = await find_git_channel(ctx.guild)
    
    if not git_channel:
        await ctx.send("❌ No git channel found. Use `!creategit`")
        return
    
    permissions = git_channel.permissions_for(ctx.guild.me)
    
    embed = discord.Embed(
        title="✅ Git Channel Test",
        description=f"Found: {git_channel.mention}",
        color=discord.Color.green()
    )
    
    embed.add_field(
        name="Permissions",
        value=(
            f"{'✅' if permissions.send_messages else '❌'} Send Messages\n"
            f"{'✅' if permissions.embed_links else '❌'} Embed Links"
        ),
        inline=False
    )
    
    await ctx.send(embed=embed)
    
    if permissions.send_messages:
        await git_channel.send(f"🧪 Test by {ctx.author.mention}")

# ============= BASIC COMMANDS =============

@bot.command()
async def hello(ctx):
    """Say hello"""
    await ctx.send(f"👋 Hello {ctx.author.mention}!")

@bot.command()
async def ping(ctx):
    """Check latency"""
    latency = round(bot.latency * 1000)
    embed = discord.Embed(title="🏓 Pong!", color=discord.Color.green())
    embed.add_field(name="Latency", value=f"{latency}ms")
    await ctx.send(embed=embed)

@bot.command()
async def serverinfo(ctx):
    """Server information"""
    guild = ctx.guild
    embed = discord.Embed(
        title=f"📊 {guild.name}",
        color=discord.Color.blue()
    )
    embed.add_field(name="Owner", value=guild.owner.mention)
    embed.add_field(name="Members", value=guild.member_count)
    embed.add_field(name="Roles", value=len(guild.roles))
    
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    
    await ctx.send(embed=embed)

# ============= AI COMMANDS =============

def chat_with_openrouter(prompt, model=None, user_id=None):
    """Chat with OpenRouter API"""
    if not OPENROUTER_API_KEY:
        return "❌ API key not set. Get one at: https://openrouter.ai/keys"
    
    model_id = FREE_MODELS.get(model or DEFAULT_MODEL, FREE_MODELS["llama"])
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    messages = [{
        "role": "system",
        "content": "You are a helpful Discord bot assistant. Be concise and friendly."
    }]
    
    if user_id and user_id in conversation_history:
        messages.extend(conversation_history[user_id][-5:])
    
    messages.append({"role": "user", "content": prompt})
    
    payload = {
        "model": model_id,
        "messages": messages,
        "max_tokens": 500,
        "temperature": 0.7
    }
    
    try:
        response = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 401:
            return "❌ Invalid API key"
        if response.status_code == 429:
            return "⏳ Rate limited. Wait a moment."
        if response.status_code != 200:
            return f"❌ API Error {response.status_code}"
        
        data = response.json()
        if 'error' in data:
            return f"❌ {data['error'].get('message', 'Error')}"
        
        ai_response = data['choices'][0]['message']['content']
        
        if user_id:
            if user_id not in conversation_history:
                conversation_history[user_id] = []
            conversation_history[user_id].append({"role": "user", "content": prompt})
            conversation_history[user_id].append({"role": "assistant", "content": ai_response})
            conversation_history[user_id] = conversation_history[user_id][-10:]
        
        return ai_response
    
    except requests.Timeout:
        return "⏱️ Timeout. Try again."
    except Exception as e:
        return f"❌ Error: {str(e)}"

@bot.command()
async def chat(ctx, *, prompt: str):
    """Chat with AI"""
    async with ctx.typing():
        reply = chat_with_openrouter(prompt, user_id=ctx.author.id)
        
        if len(reply) > 1900:
            for i in range(0, len(reply), 1900):
                await ctx.send(reply[i:i+1900])
        else:
            await ctx.send(reply)

@bot.command()
async def models(ctx):
    """List AI models"""
    embed = discord.Embed(
        title="🤖 Available Models (FREE)",
        description=f"Current: `{DEFAULT_MODEL}`",
        color=discord.Color.blue()
    )
    
    embed.add_field(name="llama", value="Fast & reliable", inline=False)
    embed.add_field(name="deepseek", value="Advanced reasoning", inline=False)
    embed.add_field(name="gemini", value="Google's latest", inline=False)
    embed.add_field(name="mistral", value="Good for coding", inline=False)
    
    await ctx.send(embed=embed)

# ============= ERROR HANDLER =============

@bot.event
async def on_command_error(ctx, error):
    """Handle errors"""
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ No permission")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing: `{error.param.name}`")
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        await ctx.send(f"❌ Error: {str(error)}")
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
    
    # Pre-load tokens into memory BEFORE starting bot
    print("📦 Pre-loading tokens from database...")
    if load_tokens_from_db():
        print(f"✅ {len(webhook_tokens_memory)} tokens loaded and ready")
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
