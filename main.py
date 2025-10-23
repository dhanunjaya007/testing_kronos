from flask import Flask, request
import threading
import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os
import requests

# Load environment variables
load_dotenv()
token = os.getenv('DISCORD_TOKEN')

# Setup logging
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

# ============= FLASK ROUTES =============

@app.route('/github', methods=['POST'])
def github_webhook():
    """Handle GitHub webhook for commit notifications"""
    data = request.json
    author = data.get('head_commit', {}).get('author', {}).get('name')
    message = data.get('head_commit', {}).get('message')
    
    if author and message:
        channel = bot.get_channel(1430206059833720853)
        if channel:
            bot.loop.create_task(channel.send(f"🔔 New commit by **{author}**: {message}"))
    
    return '', 200

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for monitoring"""
    return {'status': 'ok', 'bot_ready': bot.is_ready()}, 200

# ============= BOT EVENTS =============

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user.name} (ID: {bot.user.id})")
    print(f"Connected to {len(bot.guilds)} guild(s)")
    print(f"🤖 Using OpenRouter with model: {DEFAULT_MODEL}")
    if not OPENROUTER_API_KEY:
        print("⚠️ WARNING: OPENROUTER_API_KEY not set!")

@bot.event
async def on_member_join(member):
    """Welcome new members"""
    try:
        await member.send(f"👋 Welcome to **{member.guild.name}**! We're glad to have you here!")
    except discord.Forbidden:
        pass

@bot.event
async def on_message(message):
    """Handle message events and automatic responses"""
    if message.author == bot.user:
        return
    
    content_lower = message.content.lower()
    
    # Content moderation
    if "fuckyou" in content_lower:
        try:
            await message.delete()
            await message.channel.send(f"{message.author.mention} fuck you too! 😤", delete_after=5)
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
    await ctx.send(f"🏓 Pong! Latency: {latency}ms")

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
    if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
        await ctx.send("❌ You cannot kick someone with an equal or higher role.")
        return
    
    await member.kick(reason=reason)
    await ctx.send(f"👢 {member.mention} has been kicked. Reason: {reason or 'No reason provided'}")

@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason=None):
    """Ban a member from the server"""
    if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
        await ctx.send("❌ You cannot ban someone with an equal or higher role.")
        return
    
    if not ctx.guild.me.guild_permissions.ban_members:
        await ctx.send("❌ I don't have permission to ban members.")
        return
    
    await member.ban(reason=reason)
    await ctx.send(f"🔨 {member.mention} has been banned. Reason: {reason or 'No reason provided'}")

@bot.command()
@commands.has_permissions(ban_members=True)
async def unban(ctx, user_id: int):
    """Unban a user using their Discord ID"""
    try:
        user = discord.Object(id=user_id)
        await ctx.guild.unban(user)
        await ctx.send(f"✅ Successfully unbanned user with ID {user_id}.")
    except discord.NotFound:
        await ctx.send("❌ That user is not in the ban list.")
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
    
    await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f"🧹 Deleted {amount} messages.", delete_after=5)

@bot.command()
@commands.has_permissions(manage_roles=True)
async def mute(ctx, member: discord.Member, *, reason=None):
    """Mute a member in the server"""
    muted_role = discord.utils.get(ctx.guild.roles, name="Muted")
    
    if not muted_role:
        muted_role = await ctx.guild.create_role(name="Muted")
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

# ============= OPENROUTER AI FUNCTIONS =============

def chat_with_openrouter(prompt, model=None):
    """Chat using OpenRouter API"""
    if not OPENROUTER_API_KEY:
        return "❌ OpenRouter API key not configured.\n\n📝 Get your FREE API key at: https://openrouter.ai/keys\nThen add it to your .env file as: OPENROUTER_API_KEY=your_key_here"
    
    model_id = FREE_MODELS.get(model or DEFAULT_MODEL, FREE_MODELS["llama"])
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/yourusername/discord-bot",
        "X-Title": "Discord Bot"
    }
    
    payload = {
        "model": model_id,
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful, friendly assistant in a Discord server. Keep responses concise and engaging."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "max_tokens": 300,
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
        
        return data['choices'][0]['message']['content']
    
    except requests.Timeout:
        return "⏱️ Request timed out. Please try again."
    except Exception as e:
        return f"❌ Error: {str(e)}"

# ============= AI CHAT COMMANDS =============

@bot.command()
async def chat(ctx, *, prompt: str):
    """Chat with AI using OpenRouter"""
    async with ctx.typing():
        reply = chat_with_openrouter(prompt)
        
        # Split long messages
        if len(reply) > 1900:
            chunks = [reply[i:i+1900] for i in range(0, len(reply), 1900)]
            for chunk in chunks:
                await ctx.send(chunk)
        else:
            await ctx.send(reply)

@bot.command()
async def models(ctx):
    """List available AI models"""
    models_info = f"""
🤖 **Available OpenRouter Models (All FREE!):**

1️⃣ **Llama 3.2** (Default) - `llama`
   - Fast and reliable
   - Great for general chat

2️⃣ **DeepSeek R1** - `deepseek`
   - Advanced reasoning
   - Powerful 70B model

3️⃣ **Gemini 2.0 Flash** - `gemini`
   - Google's latest model
   - Very fast responses

4️⃣ **Mistral 7B** - `mistral`
   - Efficient and smart
   - Good for coding

**Current Model:** `{DEFAULT_MODEL}`

To switch: `!model <name>`
Example: `!model deepseek`

Try: `!chat Tell me a joke`
    """
    await ctx.send(models_info)

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
    await ctx.send(f"✅ Switched to **{model_name.upper()}** model!")

@bot.command()
async def aihelp(ctx):
    """Get help with AI commands"""
    help_text = """
🤖 **AI Commands Help:**

**Basic Usage:**
`!chat <your message>` - Chat with AI
`!models` - List all available models
`!model <name>` - Switch model (admin only)

**Examples:**
• `!chat What's the weather like?`
• `!chat Write a short poem about coding`
• `!chat Explain quantum physics simply`

**Setup Guide:**
If the bot isn't responding:
1. Get a FREE API key: https://openrouter.ai/keys
2. Add to .env: `OPENROUTER_API_KEY=your_key_here`
3. Restart the bot

**Free Models:** Llama, DeepSeek, Gemini, Mistral
All completely free, no credit card needed! 🎉
    """
    await ctx.send(help_text)

# ============= ERROR HANDLERS =============

@bot.event
async def on_command_error(ctx, error):
    """Handle command errors"""
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to use this command.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing required argument: {error.param.name}")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Invalid argument provided.")
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        await ctx.send(f"❌ An error occurred: {str(error)}")
        print(f"Error: {error}")

# ============= RUN BOT AND FLASK =============

def run_bot():
    """Run the Discord bot"""
    bot.run(token, log_handler=handler, log_level=logging.DEBUG)

def run_flask():
    """Run the Flask app"""
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    # Start bot in a separate thread
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Run Flask in main thread
    run_flask()
