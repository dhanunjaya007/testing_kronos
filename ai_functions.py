import discord
from discord import app_commands
from discord.ext import commands
import requests
import logging

logger = logging.getLogger(__name__)

# Store conversation history per user
conversation_history = {}

# Store user's preferred model (user_id: model_name)
user_models = {}

# ============= AI HELPER FUNCTIONS =============

def chat_with_openrouter(prompt, model=None, user_id=None, OPENROUTER_API_KEY=None, 
                         OPENROUTER_URL=None, FREE_MODELS=None, DEFAULT_MODEL=None):
    """Chat with OpenRouter API"""
    if not OPENROUTER_API_KEY:
        return "❌ API key not set. Get one at: https://openrouter.ai/keys"

    # Use user's preferred model if set, otherwise use specified or default
    if user_id and user_id in user_models:
        model = user_models[user_id]
    
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

# ============= AI BOT COMMANDS =============

def setup_ai_commands(bot, OPENROUTER_API_KEY, OPENROUTER_URL, FREE_MODELS, DEFAULT_MODEL):
    """Set up AI-related bot commands"""

    @bot.hybrid_command(name="chat", description="Chat with AI")
    @app_commands.describe(prompt="Your message to the AI")
    async def chat(ctx: commands.Context, *, prompt: str):
        """Chat with AI"""
        await ctx.defer()

        reply = chat_with_openrouter(
            prompt,
            user_id=ctx.author.id,
            OPENROUTER_API_KEY=OPENROUTER_API_KEY,
            OPENROUTER_URL=OPENROUTER_URL,
            FREE_MODELS=FREE_MODELS,
            DEFAULT_MODEL=DEFAULT_MODEL
        )

        if len(reply) > 1900:
            for i in range(0, len(reply), 1900):
                await ctx.send(reply[i:i+1900])
        else:
            await ctx.send(reply)

    @bot.hybrid_command(name="models", description="List available AI models")
    async def models(ctx: commands.Context):
        """List AI models"""
        # Get user's current model
        current_model = user_models.get(ctx.author.id, DEFAULT_MODEL)
        
        embed = discord.Embed(
            title="🤖 Available AI Models (FREE)",
            description=f"**Your Current Model:** `{current_model}`\n\nUse `/setmodel <name>` to switch",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="llama", 
            value="Meta LLaMA 3.2 - Fast & reliable" + (" ✅ *Active*" if current_model == "llama" else ""), 
            inline=False
        )
        embed.add_field(
            name="deepseek", 
            value="DeepSeek R1 - Advanced reasoning" + (" ✅ *Active*" if current_model == "deepseek" else ""), 
            inline=False
        )
        embed.add_field(
            name="gemini", 
            value="Google Gemini 2.0 - Google's latest" + (" ✅ *Active*" if current_model == "gemini" else ""), 
            inline=False
        )
        embed.add_field(
            name="mistral", 
            value="Mistral 7B - Good for coding" + (" ✅ *Active*" if current_model == "mistral" else ""), 
            inline=False
        )

        await ctx.send(embed=embed)

    @bot.hybrid_command(name="setmodel", description="Switch AI model")
    @app_commands.describe(model="Model to use (llama/deepseek/gemini/mistral)")
    @app_commands.choices(model=[
        app_commands.Choice(name="LLaMA 3.2 (Fast & Reliable)", value="llama"),
        app_commands.Choice(name="DeepSeek R1 (Advanced Reasoning)", value="deepseek"),
        app_commands.Choice(name="Gemini 2.0 (Google's Latest)", value="gemini"),
        app_commands.Choice(name="Mistral 7B (Good for Coding)", value="mistral")
    ])
    async def setmodel(ctx: commands.Context, model: str):
        """Switch AI model"""
        if model not in FREE_MODELS:
            await ctx.send(f"❌ Invalid model. Choose from: {', '.join(FREE_MODELS.keys())}", ephemeral=True)
            return
        
        # Save user's preference
        user_models[ctx.author.id] = model
        
        # Get model details
        model_names = {
            "llama": "Meta LLaMA 3.2",
            "deepseek": "DeepSeek R1",
            "gemini": "Google Gemini 2.0",
            "mistral": "Mistral 7B"
        }
        
        embed = discord.Embed(
            title="✅ AI Model Changed",
            description=f"Now using: **{model_names[model]}**",
            color=discord.Color.green()
        )
        embed.add_field(name="Model ID", value=f"`{model}`", inline=False)
        embed.set_footer(text="Your conversations will continue with this model")
        
        await ctx.send(embed=embed)

    @bot.hybrid_command(name="currentmodel", description="Check your current AI model")
    async def currentmodel(ctx: commands.Context):
        """Check current model"""
        current_model = user_models.get(ctx.author.id, DEFAULT_MODEL)
        
        model_names = {
            "llama": "Meta LLaMA 3.2",
            "deepseek": "DeepSeek R1",
            "gemini": "Google Gemini 2.0",
            "mistral": "Mistral 7B"
        }
        
        embed = discord.Embed(
            title="🤖 Your Current AI Model",
            description=f"**{model_names[current_model]}**",
            color=discord.Color.blue()
        )
        embed.add_field(name="Model ID", value=f"`{current_model}`", inline=False)
        embed.add_field(name="Switch Models", value="Use `/setmodel` to change", inline=False)
        
        await ctx.send(embed=embed)

    @bot.hybrid_command(name="reset", description="Reset your conversation history")
    async def reset(ctx: commands.Context):
        """Reset conversation history for the user"""
        if ctx.author.id in conversation_history:
            conversation_history.pop(ctx.author.id)
            await ctx.send("✅ Your conversation history has been reset!", ephemeral=True)
        else:
            await ctx.send("ℹ️ You don't have any conversation history.", ephemeral=True)
