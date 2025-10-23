from flask import Flask, request, jsonify
import threading
import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os
import requests
import asyncio

# Load environment variables
load_dotenv()
token = os.getenv('DISCORD_TOKEN')

# Setup logging
logging.basicConfig(level=logging.INFO)
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

# Store conversation history (optional enhancement)
conversation_history = {}

# Bot running flag
bot_thread = None

# ============= FLASK ROUTES =============

@app.route('/github', methods=['POST'])
def github_webhook():
    """Handle GitHub webhook for commit notifications"""
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'No JSON data received'}), 400
        
        author = data.get('head_commit', {}).get('author', {}).get('name')
        message = data.get('head_commit', {}).get('message')
        
        if author and message and bot.is_ready():
            channel = bot.get_channel(1430206059833720853)
            if channel:
                asyncio.run_coroutine_threadsafe(
                    channel.send(f"🔔 New commit by **{author}**: {message}"),
                    bot.loop
                )
        
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        logging.error(f"GitHub webhook error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for monitoring"""
    return jsonify({
        'status': 'ok',
        'bot_ready': bot.is_ready(),
        'bot_latency': round(bot.latency * 1000) if bot.is_ready() else None,
        'guilds': len(bot.guilds) if bot.is_ready() else 0
    }), 200

@app.route('/', methods=['GET'])
def home():
    """Basic home route"""
    return jsonify({
        'bot': 'Discord Bot with AI',
        'status': 'running',
        'bot_online': bot.is_ready(),
        'endpoints': ['/health', '/github']
    }), 200

# ============= BOT EVENTS =============

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user.name} (ID: {bot.user.id})")
    print(f"Connected to {len(bot.guilds)} guild(s)")
    print(f"🤖 Using OpenRouter with model: {DEFAULT_MODEL}")
    if not OPENROUTER_API_KEY:
        print("⚠️ WARNING: OPENROUTER_API_KEY not set! AI commands will not work.")
    
    # Set bot status
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.listening,
            name="!help | AI-powered"
        )
    )

@bot.event
async def on_member_join(member):
    """Welcome new members"""
    try:
        # Send DM
        await member.send(
            f"👋 Welcome to **{member.guild.name}**! We're glad to have you here!\n"
            f"Type `!help` to see available commands."
        )
        
        # Send message to system channel if available
        if member.guild.system_channel:
            await member.guild.system_channel.send(
                f"👋 Welcome {member.mention} to the server!"
            )
    except discord.Forbidden:
        pass

@bot.event
async def on_message(message):
    """Handle message events and automatic responses"""
    if message.author == bot.user:
        return
    
    content_lower = message.content.lower()
    
    # Content moderation
    if "fuckyou" in content_lower.replace(" ", ""):
        try:
            await message.delete()
            await message.channel.send(
                f"{message.author.mention} Please keep it friendly! 😊",
                delete_after=5
            )
        except discord.Forbidden:
            pass
    
    # Positive response
    if "love you" in content_lower and not message.content.startswith('!'):
        await message.channel.send(f"{message.author.mention} I love you too! ❤️")
    
    await bot.process_commands(message)

# ============= BASIC COMMANDS =============

@bot.command()
async def hello(ctx):
    """Say hello to the user"""
    await ctx.send(f"👋 Hello {ctx.author.mention}!")

@bot.command()
async def ping(ctx):
    """Check bot latency"""
    latency = round(bot.latency * 1000)
    embed = discord.Embed(title="🏓 Pong!", color=discord.Color.green())
    embed.add_field(name="Latency", value=f"{latency}ms")
    await ctx.send(embed=embed)

@bot.command()
async def serverinfo(ctx):
    """Display server information"""
    guild = ctx.guild
    embed = discord.Embed(
        title=f"📊 {guild.name} Server Info",
        color=discord.Color.blue()
    )
    embed.add_field(name="Owner", value=guild.owner.mention, inline=True)
    embed.add_field(name="Members", value=guild.member_count, inline=True)
    embed.add_field(name="Roles", value=len(guild.roles), inline=True)
    embed.add_field(name="Created", value=guild.created_at.strftime("%Y-%m-%d"), inline=True)
    
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    
    await ctx.send(embed=embed)

# ============= ROLE MANAGEMENT =============

@bot.command()
async def assign(ctx, role: discord.Role, user: discord.Member = None):
    """Assign a role to yourself or another user"""
    target = user or ctx.author
    
    if user and not ctx.author.guild_permissions.manage_roles:
        await ctx.send("❌ You don't have permission to assign roles to others.")
        return
    
    if not ctx.guild.me.guild_permissions.manage_roles:
        await ctx.send("❌ I don't have permission to manage roles.")
        return
    
    if role >= ctx.guild.me.top_role:
        await ctx.send("❌ I cannot assign a role that is equal to or higher than my highest role.")
        return
    
    if role in target.roles:
        await ctx.send(f"ℹ️ {target.mention} already has the role **{role.name}**.")
        return
    
    try:
        await target.add_roles(role)
        if target == ctx.author:
            await ctx.send(f"✅ You have been given the role **{role.name}**.")
        else:
            await ctx.send(f"✅ Role **{role.name}** has been assigned to {target.mention}.")
    except Exception as e:
        await ctx.send(f"❌ Failed to add role: {e}")

@bot.command()
async def remove(ctx, role: discord.Role, user: discord.Member = None):
    """Remove a role from yourself or another user"""
    target = user or ctx.author
    
    if user and not ctx.author.guild_permissions.manage_roles:
        await ctx.send("❌ You don't have permission to remove roles from others.")
        return
    
    if not ctx.guild.me.guild_permissions.manage_roles:
        await ctx.send("❌ I don't have permission to manage roles.")
        return
    
    if role not in target.roles:
        await ctx.send(f"ℹ️ {target.mention} doesn't have the role **{role.name}**.")
        return
    
    try:
        await target.remove_roles(role)
        if target == ctx.author:
            await ctx.send(f"✅ The role **{role.name}** has been removed from you.")
        else:
            await ctx.send(f"✅ Role **{role.name}** has been removed from {target.mention}.")
    except Exception as e:
        await ctx.send(f"❌ Failed to remove role: {e}")

# ============= MODERATION COMMANDS =============

@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason=None):
    """Kick a member from the server"""
    if member == ctx.author:
        await ctx.send("❌ You cannot kick yourself.")
        return
    
    if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
        await ctx.send("❌ You cannot kick someone with an equal or higher role.")
        return
    
    if not ctx.guild.me.guild_permissions.kick_members:
        await ctx.send("❌ I don't have permission to kick members.")
        return
    
    try:
        await member.send(f"⚠️ You have been kicked from **{ctx.guild.name}**. Reason: {reason or 'No reason provided'}")
    except:
        pass
    
    await member.kick(reason=reason)
    await ctx.send(f"👢 {member.mention} has been kicked. Reason: {reason or 'No reason provided'}")

@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason=None):
    """Ban a member from the server"""
    if member == ctx.author:
        await ctx.send("❌ You cannot ban yourself.")
        return
    
    if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
        await ctx.send("❌ You cannot ban someone with an equal or higher role.")
        return
    
    if not ctx.guild.me.guild_permissions.ban_members:
        await ctx.send("❌ I don't have permission to ban members.")
        return
    
    try:
        await member.send(f"🔨 You have been banned from **{ctx.guild.name}**. Reason: {reason or 'No reason provided'}")
    except:
        pass
    
    await member.ban(reason=reason)
    await ctx.send(f"🔨 {member.mention} has been banned. Reason: {reason or 'No reason provided'}")

@bot.command()
@commands.has_permissions(ban_members=True)
async def unban(ctx, user_id: int):
    """Unban a user using their Discord ID"""
    try:
        user = await bot.fetch_user(user_id)
        await ctx.guild.unban(user)
        await ctx.send(f"✅ Successfully unbanned **{user.name}** (ID: {user_id}).")
    except discord.NotFound:
        await ctx.send("❌ That user is not in the ban list or doesn't exist.")
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to unban users.")
    except Exception as e:
        await ctx.send(f"❌ Unexpected error: {e}")

@bot.command()
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int = 5):
    """Clear a specific number of messages from the chat"""
    if amount < 1 or amount > 100:
        await ctx.send("❌ Please specify a number between 1 and 100.")
        return
    
    deleted = await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f"🧹 Deleted {len(deleted) - 1} messages.", delete_after=5)

@bot.command()
@commands.has_permissions(manage_roles=True)
async def mute(ctx, member: discord.Member, *, reason=None):
    """Mute a member in the server"""
    muted_role = discord.utils.get(ctx.guild.roles, name="Muted")
    
    if not muted_role:
        muted_role = await ctx.guild.create_role(name="Muted", reason="Mute command setup")
        for channel in ctx.guild.channels:
            await channel.set_permissions(muted_role, send_messages=False, speak=False, add_reactions=False)
    
    if muted_role in member.roles:
        await ctx.send(f"❌ {member.mention} is already muted.")
        return
    
    await member.add_roles(muted_role, reason=reason)
    await ctx.send(f"🔇 {member.mention} has been muted. Reason: {reason or 'No reason provided'}")

@bot.command()
@commands.has_permissions(manage_roles=True)
async def unmute(ctx, member: discord.Member):
    """Unmute a member in the server"""
    muted_role = discord.utils.get(ctx.guild.roles, name="Muted")
    
    if not muted_role or muted_role not in member.roles:
        await ctx.send(f"❌ {member.mention} is not muted.")
        return
    
    await member.remove_roles(muted_role)
    await ctx.send(f"🔊 {member.mention} has been unmuted.")

@bot.command()
@commands.has_permissions(manage_messages=True)
async def warn(ctx, member: discord.Member, *, reason=None):
    """Warn a user via DM"""
    try:
        await member.send(f"⚠️ You have been warned in **{ctx.guild.name}** for: {reason or 'No reason provided'}")
        await ctx.send(f"✅ {member.mention} has been warned for: {reason or 'No reason provided'}")
    except discord.Forbidden:
        await ctx.send(f"⚠️ {member.mention} has been warned for: {reason or 'No reason provided'} (Could not send DM)")

# ============= UTILITY COMMANDS =============

@bot.command()
async def dm(ctx, *, msg):
    """Send yourself a DM"""
    try:
        await ctx.author.send(f"{msg}\n\nLove you! ❤️")
        await ctx.send("✅ DM sent! Check your messages.", delete_after=5)
    except discord.Forbidden:
        await ctx.send("❌ I couldn't send you a DM. Please enable DMs from server members.")
    except Exception as e:
        await ctx.send(f"❌ Failed to send DM: {e}")

@bot.command()
async def userinfo(ctx, member: discord.Member = None):
    """Display information about a user"""
    member = member or ctx.author
    
    embed = discord.Embed(
        title=f"👤 {member.name}",
        color=member.color
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="ID", value=member.id, inline=True)
    embed.add_field(name="Nickname", value=member.nick or "None", inline=True)
    embed.add_field(name="Status", value=str(member.status).title(), inline=True)
    embed.add_field(name="Joined Server", value=member.joined_at.strftime("%Y-%m-%d"), inline=True)
    embed.add_field(name="Account Created", value=member.created_at.strftime("%Y-%m-%d"), inline=True)
    embed.add_field(name="Roles", value=f"{len(member.roles) - 1}", inline=True)
    
    await ctx.send(embed=embed)

# ============= OPENROUTER AI FUNCTIONS =============

def chat_with_openrouter(prompt, model=None, user_id=None):
    """Chat using OpenRouter API with conversation context"""
    if not OPENROUTER_API_KEY:
        return "❌ OpenRouter API key not configured.\n\n📝 Get your FREE API key at: https://openrouter.ai/keys\nThen add it to your .env file as: OPENROUTER_API_KEY=your_key_here"
    
    model_id = FREE_MODELS.get(model or DEFAULT_MODEL, FREE_MODELS["llama"])
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/yourusername/discord-bot",
        "X-Title": "Discord Bot"
    }
    
    # Build messages with conversation history
    messages = [
        {
            "role": "system",
            "content": "You are a helpful, friendly assistant in a Discord server. Keep responses concise and engaging. Be conversational and helpful."
        }
    ]
    
    # Add conversation history if available (last 5 messages)
    if user_id and user_id in conversation_history:
        messages.extend(conversation_history[user_id][-5:])
    
    messages.append({
        "role": "user",
        "content": prompt
    })
    
    payload = {
        "model": model_id,
        "messages": messages,
        "max_tokens": 500,
        "temperature": 0.7
    }
    
    try:
        response = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 401:
            return "❌ Invalid API key. Please check your OPENROUTER_API_KEY in .env file."
        
        if response.status_code == 429:
            return "⏳ Rate limit reached. Please wait a moment and try again."
        
        if response.status_code != 200:
            return f"❌ API Error {response.status_code}: {response.text[:200]}"
        
        data = response.json()
        
        if 'error' in data:
            return f"❌ Error: {data['error'].get('message', 'Unknown error')}"
        
        ai_response = data['choices'][0]['message']['content']
        
        # Store conversation history
        if user_id:
            if user_id not in conversation_history:
                conversation_history[user_id] = []
            
            conversation_history[user_id].append({"role": "user", "content": prompt})
            conversation_history[user_id].append({"role": "assistant", "content": ai_response})
            
            # Keep only last 10 messages
            conversation_history[user_id] = conversation_history[user_id][-10:]
        
        return ai_response
    
    except requests.Timeout:
        return "⏱️ Request timed out. Please try again."
    except Exception as e:
        logging.error(f"OpenRouter API error: {e}")
        return f"❌ Error: {str(e)}"

# ============= AI CHAT COMMANDS =============

@bot.command()
async def chat(ctx, *, prompt: str):
    """Chat with AI using OpenRouter"""
    async with ctx.typing():
        reply = chat_with_openrouter(prompt, user_id=ctx.author.id)
        
        # Split long messages
        if len(reply) > 1900:
            chunks = [reply[i:i+1900] for i in range(0, len(reply), 1900)]
            for chunk in chunks:
                await ctx.send(chunk)
        else:
            await ctx.send(reply)

@bot.command()
async def askwith(ctx, model: str, *, prompt: str):
    """Chat with a specific AI model"""
    if model.lower() not in FREE_MODELS:
        await ctx.send(f"❌ Invalid model. Choose from: {', '.join(FREE_MODELS.keys())}")
        return
    
    async with ctx.typing():
        reply = chat_with_openrouter(prompt, model=model.lower(), user_id=ctx.author.id)
        
        if len(reply) > 1900:
            chunks = [reply[i:i+1900] for i in range(0, len(reply), 1900)]
            for chunk in chunks:
                await ctx.send(chunk)
        else:
            await ctx.send(reply)

@bot.command()
async def clearhistory(ctx):
    """Clear your conversation history with the AI"""
    if ctx.author.id in conversation_history:
        del conversation_history[ctx.author.id]
        await ctx.send("✅ Your conversation history has been cleared!")
    else:
        await ctx.send("ℹ️ You don't have any conversation history.")

@bot.command()
async def models(ctx):
    """List available AI models"""
    embed = discord.Embed(
        title="🤖 Available OpenRouter Models (All FREE!)",
        description=f"**Current Default Model:** `{DEFAULT_MODEL}`",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="1️⃣ Llama 3.2 (`llama`)",
        value="Fast and reliable\nGreat for general chat",
        inline=False
    )
    embed.add_field(
        name="2️⃣ DeepSeek R1 (`deepseek`)",
        value="Advanced reasoning\nPowerful 70B model",
        inline=False
    )
    embed.add_field(
        name="3️⃣ Gemini 2.0 Flash (`gemini`)",
        value="Google's latest model\nVery fast responses",
        inline=False
    )
    embed.add_field(
        name="4️⃣ Mistral 7B (`mistral`)",
        value="Efficient and smart\nGood for coding",
        inline=False
    )
    
    embed.add_field(
        name="📝 Commands",
        value=(
            "`!chat <message>` - Chat with default model\n"
            "`!askwith <model> <message>` - Use specific model\n"
            "`!model <name>` - Switch default (admin)\n"
            "`!clearhistory` - Clear your chat history"
        ),
        inline=False
    )
    
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(administrator=True)
async def model(ctx, model_name: str):
    """Switch AI model (admin only)"""
    global DEFAULT_MODEL
    model_name = model_name.lower()
    
    if model_name not in FREE_MODELS:
        await ctx.send(f"❌ Invalid model. Choose from: {', '.join(FREE_MODELS.keys())}\nUse `!models` to see details.")
        return
    
    DEFAULT_MODEL = model_name
    await ctx.send(f"✅ Switched default model to **{model_name.upper()}**!")

@bot.command()
async def aihelp(ctx):
    """Get help with AI commands"""
    embed = discord.Embed(
        title="🤖 AI Commands Help",
        description="All models are completely free, no credit card needed! 🎉",
        color=discord.Color.green()
    )
    
    embed.add_field(
        name="Basic Commands",
        value=(
            "`!chat <message>` - Chat with AI\n"
            "`!askwith <model> <message>` - Use specific model\n"
            "`!models` - List all models\n"
            "`!clearhistory` - Clear chat history\n"
            "`!model <name>` - Switch model (admin)"
        ),
        inline=False
    )
    
    embed.add_field(
        name="Examples",
        value=(
            "• `!chat What's the weather like?`\n"
            "• `!chat Write a poem about coding`\n"
            "• `!askwith deepseek Explain quantum physics`"
        ),
        inline=False
    )
    
    embed.add_field(
        name="Setup Guide",
        value=(
            "1. Get FREE API key: https://openrouter.ai/keys\n"
            "2. Add to .env: `OPENROUTER_API_KEY=your_key`\n"
            "3. Restart the bot"
        ),
        inline=False
    )
    
    await ctx.send(embed=embed)

# ============= ERROR HANDLERS =============

@bot.event
async def on_command_error(ctx, error):
    """Handle command errors"""
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to use this command.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing required argument: `{error.param.name}`\nUse `!help {ctx.command}` for more info.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f"❌ Invalid argument provided.\nUse `!help {ctx.command}` for more info.")
    elif isinstance(error, commands.CommandNotFound):
        pass  # Ignore unknown commands
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"⏱️ This command is on cooldown. Try again in {error.retry_after:.1f}s")
    else:
        await ctx.send(f"❌ An error occurred: {str(error)}")
        logging.error(f"Command error in {ctx.command}: {error}", exc_info=True)

# ============= BOT STARTUP FUNCTION =============

def start_bot():
    """Start the Discord bot in a separate thread"""
    global bot_thread
    
    if not token:
        print("❌ ERROR: DISCORD_TOKEN not found in environment variables!")
        return
    
    def run_bot():
        try:
            print("🤖 Starting Discord bot...")
            bot.run(token, log_handler=handler, log_level=logging.INFO)
        except Exception as e:
            logging.error(f"Failed to start bot: {e}")
    
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    print("✅ Discord bot thread started")

# ============= START BOT ON MODULE IMPORT =============

# Start the bot when the module is loaded (for gunicorn)
start_bot()

# ============= MAIN EXECUTION =============

if __name__ == "__main__":
    # This runs only when executed directly (not with gunicorn)
    print("🌐 Starting Flask and Discord bot...")
    app.run(host="0.0.0.0", port=port, debug=False)
