import secrets
import discord
from discord import app_commands
from discord.ext import commands
from flask import request, jsonify
import logging
import requests
import time

logger = logging.getLogger(__name__)

# ============= GIT HELPER FUNCTIONS =============

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
    return secrets.token_urlsafe(32)

# ============= GITHUB WEBHOOK ROUTE =============

def register_github_routes(app, bot, get_webhook_data, ensure_tokens_loaded, DEPLOYMENT_URL):
    """Register GitHub webhook routes with Flask app"""

    @app.route('/github/<token>', methods=['POST'])
    def github_webhook(token):
        """Handle GitHub webhook for commit notifications"""
        try:
            ensure_tokens_loaded()

            client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
            logger.info(f"📥 Webhook request from {client_ip} with token: {token[:10]}...")

            data = request.json
            if not data:
                return jsonify({'error': 'No JSON data received'}), 400

            event_type = request.headers.get('X-GitHub-Event', 'unknown')
            repo_name = data.get('repository', {}).get('name', 'Unknown')
            logger.info(f"📦 GitHub event: {event_type} from repo: {repo_name}")

            webhook_info = get_webhook_data(token)
            if not webhook_info:
                logger.warning(f"❌ Invalid webhook token: {token[:10]}...")
                return jsonify({'error': 'Invalid webhook token'}), 403

            webhook_url = webhook_info['webhook_url']
            guild_id = webhook_info['guild_id']
            logger.info(f"✅ Valid token for guild {guild_id}")

            if event_type == 'ping':
                logger.info(f"✅ GitHub ping successful for guild {guild_id}")
                return jsonify({
                    'status': 'success',
                    'message': 'Webhook configured successfully!',
                    'guild_id': guild_id
                }), 200

            commits = data.get('commits', [])
            repository = data.get('repository', {})
            repo_name = repository.get('name', 'Unknown Repository')
            repo_url = repository.get('html_url', '')
            pusher = data.get('pusher', {}).get('name', 'Unknown')
            ref = data.get('ref', '').split('/')[-1]

            if commits:
                embeds = []
                total_commits = len(commits)

                for i in range(0, min(total_commits, 50), 5):
                    batch_start = i + 1
                    batch_end = min(i + 5, total_commits)

                    embed = {
                        "title": f"🔔 New Push to {repo_name}",
                        "url": repo_url,
                        "color": 3447003,
                        "description": f"**Commits {batch_start}-{batch_end}** of **{total_commits}** pushed to `{ref}` by **{pusher}**",
                        "fields": []
                    }

                    for commit in commits[i:i+5]:
                        author = commit.get('author', {}).get('name', 'Unknown')
                        message = commit.get('message', 'No message')
                        commit_url = commit.get('url', '')
                        commit_id = commit.get('id', '')[:7]

                        if len(message) > 100:
                            message = message[:97] + "..."

                        embed["fields"].append({
                            "name": f"`{commit_id}` - {author}",
                            "value": f"[{message}]({commit_url})",
                            "inline": False
                        })

                    embeds.append(embed)

                for embed in embeds:
                    try:
                        response = requests.post(
                            webhook_url,
                            json={"embeds": [embed]},
                            headers={"Content-Type": "application/json"},
                            timeout=30
                        )

                        if response.status_code not in [204, 200]:
                            logger.error(f"❌ Discord webhook returned {response.status_code}")
                            return jsonify({'error': 'Failed to send to Discord'}), 500
                    except Exception as e:
                        logger.error(f"❌ Error sending to Discord webhook: {e}")
                        return jsonify({'error': 'Failed to send to Discord'}), 500

                    time.sleep(0.5)

                if total_commits > 50:
                    try:
                        requests.post(
                            webhook_url,
                            json={"content": f"⚠️ **{total_commits - 50}** more commits not shown. View at {repo_url}"},
                            timeout=30
                        )
                    except:
                        pass
            else:
                try:
                    requests.post(
                        webhook_url,
                        json={"content": f"🔔 GitHub event (`{event_type}`) from **{repo_name}** by **{pusher}**"},
                        timeout=30
                    )
                except Exception as e:
                    logger.error(f"❌ Error sending to Discord webhook: {e}")
                    return jsonify({'error': 'Failed to send to Discord'}), 500

            return jsonify({
                'status': 'success',
                'guild_id': guild_id,
                'commits_processed': len(commits)
            }), 200

        except Exception as e:
            logger.error(f"❌ GitHub webhook error: {e}", exc_info=True)
            return jsonify({'error': 'Internal server error', 'message': str(e)}), 500

# ============= GIT BOT COMMANDS =============

def setup_git_commands(bot, save_webhook_data, DEPLOYMENT_URL):
    """Set up GitHub-related bot commands"""

    @bot.hybrid_command(name="setupgit", description="Set up GitHub webhook integration (Admin only)")
    @app_commands.checks.has_permissions(administrator=True)
    async def setupgit(ctx: commands.Context):
        """Set up GitHub webhook"""
        guild = ctx.guild
        git_channel = await find_git_channel(guild)

        if not git_channel:
            embed = discord.Embed(
                title="❌ No 'git' Channel",
                description="Create a channel named `git` first!\nUse `/creategit`",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed, ephemeral=True)
            return

        if not git_channel.permissions_for(guild.me).manage_webhooks:
            embed = discord.Embed(
                title="❌ Missing Permissions",
                description="I need **Manage Webhooks** permission in the git channel!",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed, ephemeral=True)
            return

        try:
            discord_webhook = await git_channel.create_webhook(
                name="GitHub Notifications",
                reason=f"GitHub integration setup by {ctx.author}"
            )

            logger.info(f"✅ Created Discord webhook for guild {guild.id}")

            token = generate_webhook_token(guild.id)
            save_webhook_data(
                token=token,
                guild_id=guild.id,
                webhook_url=discord_webhook.url,
                webhook_id=discord_webhook.id,
                webhook_token=discord_webhook.token
            )

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
                await ctx.send("✅ Sent to your DMs! 📬", ephemeral=True, delete_after=10)
            except discord.Forbidden:
                await ctx.send("⚠️ Couldn't DM you!", embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"❌ Error creating webhook: {e}", exc_info=True)
            await ctx.send(f"❌ Error: {str(e)}", ephemeral=True)

    @bot.hybrid_command(name="creategit", description="Create a 'git' channel (Admin only)")
    @app_commands.checks.has_permissions(administrator=True)
    async def creategit(ctx: commands.Context):
        """Create a 'git' channel"""
        guild = ctx.guild
        git_channel = await find_git_channel(guild)

        if git_channel:
            await ctx.send(f"ℹ️ Git channel exists: {git_channel.mention}", ephemeral=True)
            return

        try:
            new_channel = await guild.create_text_channel(
                name='git',
                topic='📦 GitHub notifications',
                reason=f'Created by {ctx.author}'
            )

            embed = discord.Embed(
                title="✅ Git Channel Created!",
                description=f"{new_channel.mention} ready for GitHub!\nUse `/setupgit` next.",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)
            await new_channel.send("🎉 Git channel ready! Use `/setupgit` to connect GitHub.")

        except discord.Forbidden:
            await ctx.send("❌ No permission to create channels.", ephemeral=True)
        except Exception as e:
            await ctx.send(f"❌ Error: {e}", ephemeral=True)

    @bot.hybrid_command(name="testgit", description="Test git channel configuration")
    async def testgit(ctx: commands.Context):
        """Test git channel"""
        git_channel = await find_git_channel(ctx.guild)

        if not git_channel:
            await ctx.send("❌ No git channel found. Use `/creategit`", ephemeral=True)
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
                f"{'✅' if permissions.embed_links else '❌'} Embed Links\n"
                f"{'✅' if permissions.manage_webhooks else '❌'} Manage Webhooks"
            ),
            inline=False
        )

        await ctx.send(embed=embed)

        if permissions.send_messages:
            await git_channel.send(f"🧪 Test by {ctx.author.mention}")

    @setupgit.error
    @creategit.error
    async def admin_error(ctx: commands.Context, error):
        if isinstance(error, app_commands.MissingPermissions):
            await ctx.send("❌ You need Administrator permission to use this command.", ephemeral=True)
