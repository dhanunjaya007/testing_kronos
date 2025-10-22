from flask import Flask, request
import threading
import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os   

load_dotenv()
token = os.getenv('DISCORD_TOKEN')

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)
app = Flask(__name__)

@app.route('/github', methods=['POST'])
def github_webhook():
    data = request.json
    # Extract useful commit info
    author = data['head_commit']['author']['name'] if 'head_commit' in data else None
    message = data['head_commit']['message'] if 'head_commit' in data else None
    if author and message:
        # Use bot.loop for thread-safe Discord calls
        channel = bot.get_channel(1430206059833720853)
        bot.loop.create_task(channel.send(f"New commit by {author}: {message}"))
    return '', 200

def run_flask():
    app.run(host='0.0.0.0', port=5000)

flask_thread = threading.Thread(target=run_flask)
flask_thread.start()

@bot.event 
async def on_ready():
    print(f"Logged in as {bot.user.name}")
          
@bot.event 
async def on_member_join(member):
    await member.send("Welcome to the server!")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    if "fuckyou" in message .content.lower():
        await message.delete()
        await message.channel.send(f"{message.author.mention} fuck you too!")
    if "love you" in message .content.lower():
        await message.channel.send(f"{message.author.mention} I love you too!") 
    await bot.process_commands(message)

@bot.command()
async def hello(ctx):
    await ctx.send(f"Hello {ctx.author.mention}!")

@bot.command()
async def assign(ctx, role: discord.Role, user: discord.Member = None):
    target = user or ctx.author

    # If assigning to someone else, ensure the invoker has permission
    if user and not ctx.author.guild_permissions.manage_roles:
        await ctx.send("You don't have permission to assign roles to others.")
        return

    # Ensure the bot can manage roles
    if not ctx.guild.me.guild_permissions.manage_roles:
        await ctx.send("I don't have permission to manage roles.")
        return

    try:
        await target.add_roles(role)
    except Exception as e:
        await ctx.send(f"Failed to add role: {e}")
        return

    if target == ctx.author:
        await ctx.send(f"You have been given the role {role.name}.")
    else:
        await ctx.send(f"Role {role.name} has been assigned to {target.mention}.")
@bot.command()
async def remove(ctx, role: discord.Role, user: discord.Member = None):
    target = user or ctx.author

    # If removing from someone else, ensure the invoker has permission
    if user and not ctx.author.guild_permissions.manage_roles:
        await ctx.send("You don't have permission to remove roles from others.")
        return

    # Ensure the bot can manage roles
    if not ctx.guild.me.guild_permissions.manage_roles:
        await ctx.send("I don't have permission to manage roles.")
        return

    try:
        await target.remove_roles(role)
    except Exception as e:
        await ctx.send(f"Failed to remove role: {e}")
        return

    if target == ctx.author:
        await ctx.send(f"The role {role.name} has been removed from you.")
    else:
        await ctx.send(f"Role {role.name} has been removed from {target.mention}.")

@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason=None):
    """Kick a member from the server."""
    await member.kick(reason=reason)
    await ctx.send(f"{member.mention} has been kicked. Reason: {reason or 'No reason provided'}")

@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason=None):
    """Ban a member from the server."""
    await member.ban(reason=reason)
    await ctx.send(f"{member.mention} has been banned. Reason: {reason or 'No reason provided'}")

@bot.command()
@commands.has_permissions(ban_members=True)
async def unban(ctx, *, user_name):
    """Unban a user by name#discriminator."""
    banned_users = await ctx.guild.bans()
    name, discriminator = user_name.split("#")
    for entry in banned_users:
        user = entry.user
        if (user.name, user.discriminator) == (name, discriminator):
            await ctx.guild.unban(user)
            await ctx.send(f"Unbanned {user.mention}")
            return
    await ctx.send("User not found.")

@bot.command()
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int = 5):
    """Clear a specific number of messages from the chat."""
    await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f"Deleted {amount} messages.", delete_after=5)

@bot.command()
@commands.has_permissions(manage_roles=True)
async def mute(ctx, member: discord.Member, *, reason=None):
    """Mute a member by adding a 'Muted' role."""
    muted_role = discord.utils.get(ctx.guild.roles, name="Muted")
    if not muted_role:
        muted_role = await ctx.guild.create_role(name="Muted")
        for channel in ctx.guild.channels:
            await channel.set_permissions(muted_role, speak=False, send_messages=False)
    await member.add_roles(muted_role, reason=reason)
    await ctx.send(f"{member.mention} has been muted. Reason: {reason or 'No reason provided'}")

@bot.command()
@commands.has_permissions(manage_roles=True)
async def unmute(ctx, member: discord.Member):
    """Unmute a previously muted member."""
    muted_role = discord.utils.get(ctx.guild.roles, name="Muted")
    if muted_role in member.roles:
        await member.remove_roles(muted_role)
        await ctx.send(f"{member.mention} has been unmuted.")
    else:
        await ctx.send("This user isn’t muted.")

@bot.command()
@commands.has_permissions(manage_messages=True)
async def warn(ctx, member: discord.Member, *, reason=None):
    """Warn a user via DM."""
    await member.send(f"You have been warned in {ctx.guild.name} for: {reason or 'No reason provided'}")
    await ctx.send(f"{member.mention} has been warned for: {reason or 'No reason provided'}")


@bot.command()
async def dm(ctx,*, msg):
    try:
        await ctx.author.send(f"{msg} , love you!")
    except Exception as e:
        await ctx.author.send(f"Failed to send DM , {e}")

bot.run(token, log_handler=handler, log_level=logging.DEBUG)
