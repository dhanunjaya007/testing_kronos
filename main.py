from flask import Flask, request
import threading
import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os   
import requests


load_dotenv()
token = os.getenv('DISCORD_TOKEN')

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)
app = Flask(__name__)

import os
port = int(os.environ.get("PORT", 10000))  # Render's default is 10000

# In main.py somewhere (for manual launch/testing only):
# app.run(host="0.0.0.0", port=port)

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
    if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
        await ctx.send("You cannot ban someone with an equal or higher role.")
        return
    if not ctx.guild.me.guild_permissions.ban_members:
        await ctx.send("I don't have permission to ban members.")
        return
    await member.ban(reason=reason)
    await ctx.send(f"{member.mention} has been banned. Reason: {reason or 'No reason provided'}")

@bot.command()
@commands.has_permissions(ban_members=True)
async def unban(ctx, user_id: int):
    """Unban a user using their Discord ID (works with new username system)."""
    try:
        user = discord.Object(id=user_id)
        await ctx.guild.unban(user)
        await ctx.send(f"Successfully unbanned user with ID {user_id}.")
    except discord.NotFound:
        await ctx.send("That user is not in the ban list.")
    except discord.Forbidden:
        await ctx.send("I don’t have permission to unban users.")
    except Exception as e:
        await ctx.send(f"Unexpected error: {e}")



@bot.command()
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int = 5):
    """Clear a specific number of messages from the chat."""
    await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f"Deleted {amount} messages.", delete_after=5)

@bot.command()
@commands.has_permissions(manage_roles=True)
async def mute(ctx, member: discord.Member, *, reason=None):
    muted_role = discord.utils.get(ctx.guild.roles, name="Muted")
    if not muted_role:
        muted_role = await ctx.guild.create_role(name="Muted")
        for channel in ctx.guild.channels:
            await channel.set_permissions(muted_role, send_messages=False, speak=False, add_reactions=False)

    if muted_role in member.roles:
        await ctx.send(f"{member.mention} is already muted.")
        return

    await member.add_roles(muted_role, reason=reason)
    await ctx.send(f"{member.mention} has been muted. Reason: {reason or 'No reason provided'}")


@bot.command()
@commands.has_permissions(manage_roles=True)
async def unmute(ctx, member: discord.Member):
    muted_role = discord.utils.get(ctx.guild.roles, name="Muted")
    if muted_role not in member.roles:
        await ctx.send(f"{member.mention} is not muted.")
        return

    await member.remove_roles(muted_role)
    await ctx.send(f"{member.mention} has been unmuted.")

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

HF_API_URL = "https://api-inference.huggingface.co/models/HuggingFaceTB/SmolLM3-3B"
HF_TOKEN = os.getenv('HF_TOKEN').strip()  # Always strip whitespace just in case

def chat_with_smollm3(prompt):
    headers = {
        "Authorization": f"Bearer {HF_TOKEN}"
    }
    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": 128,
            "return_full_text": False
        }
    }
    response = requests.post(HF_API_URL, headers=headers, json=payload, timeout=60)
    if response.status_code != 200:
        return f"HF API HTTP {response.status_code}: '{response.text[:200]}'"
    try:
        data = response.json()
    except Exception as e:
        return f"API did not return JSON. Response: '{response.text[:100]}'"
    # Typical output: [{'generated_text': 'your reply'}]
    if ("error" in data):
        return f"HF API error: {data['error']}"
    elif isinstance(data, list):
        if (len(data) > 0 and "generated_text" in data[0]):
            return data[0]["generated_text"]
    return str(data)

@bot.command()
async def chat(ctx, *, prompt: str):
    await ctx.send("🧠 Got your message, processing...")
    try:
        reply = chat_with_smollm3(prompt)
        await ctx.send(reply[:1900])
    except Exception as e:
        await ctx.send(f"Error: {e}")


import threading
def run_bot():
    bot.run(token, log_handler=handler, log_level=logging.DEBUG)
threading.Thread(target=run_bot, daemon=True).start()












