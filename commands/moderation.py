import discord
from discord.ext import commands
from datetime import datetime, timedelta
import asyncio

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.muted_users = {}
        self.user_warnings = {}

    # Helper function to check if user has admin privileges
    def has_admin_or_permission(self, member, permission_name):
        """Check if member has administrator privilege or specific permission"""
        if member.guild_permissions.administrator:
            return True
        return getattr(member.guild_permissions, permission_name, False)

    # BAN
    @commands.command(name="ban")
    async def ban(self, ctx, member: discord.Member = None, *, reason="No reason provided"):
        # Check if user has ban_members permission OR administrator
        if not self.has_admin_or_permission(ctx.author, 'ban_members'):
            await ctx.send("❌ You need Ban Members permission or Administrator role.")
            return
        
        if not member:
            await ctx.send("❌ Please mention a user to ban.")
            return
        try:
            await member.ban(reason=reason)
            await ctx.send(f"🔨 {member.mention} has been **banned**.\nReason: {reason}")
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to ban this user.")
        except Exception as e:
            await ctx.send(f"❌ Could not ban user: {e}")

    # UNBAN
    @commands.command(name="unban")
    async def unban(self, ctx, *, user=None):
        # Check if user has ban_members permission OR administrator
        if not self.has_admin_or_permission(ctx.author, 'ban_members'):
            await ctx.send("❌ You need Ban Members permission or Administrator role.")
            return
        
        if not user:
            await ctx.send("❌ Please specify the username#tag or ID to unban.")
            return
        banned_users = await ctx.guild.bans()
        target = None
        for ban_entry in banned_users:
            if user.lower() in (str(ban_entry.user), ban_entry.user.name.lower(), str(ban_entry.user.id)):
                target = ban_entry.user
                break
        if not target:
            await ctx.send("❌ User not found in ban list.")
            return
        try:
            await ctx.guild.unban(target)
            await ctx.send(f"✅ Unbanned {target.mention}")
        except Exception as e:
            await ctx.send(f"❌ Could not unban: {e}")

    # KICK
    @commands.command(name="kick")
    async def kick(self, ctx, member: discord.Member = None, *, reason="No reason provided"):
        # Check if user has kick_members permission OR administrator
        if not self.has_admin_or_permission(ctx.author, 'kick_members'):
            await ctx.send("❌ You need Kick Members permission or Administrator role.")
            return
        
        if not member:
            await ctx.send("❌ Please mention a user to kick.")
            return
        try:
            await member.kick(reason=reason)
            await ctx.send(f"👢 {member.mention} was **kicked**.\nReason: {reason}")
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to kick this user.")
        except Exception as e:
            await ctx.send(f"❌ Could not kick user: {e}")

    # MUTE
    @commands.command(name="mute")
    async def mute(self, ctx, member: discord.Member = None, *, reason="No reason provided"):
        # Check if user has manage_roles permission OR administrator
        if not self.has_admin_or_permission(ctx.author, 'manage_roles'):
            await ctx.send("❌ You need Manage Roles permission or Administrator role.")
            return
        
        if not member:
            await ctx.send("❌ Please mention a user to mute.")
            return
        mute_role = discord.utils.get(ctx.guild.roles, name="Muted")
        try:
            if not mute_role:
                mute_role = await ctx.guild.create_role(name="Muted")
                for channel in ctx.guild.channels:
                    await channel.set_permissions(mute_role, speak=False, send_messages=False)
            if mute_role in member.roles:
                await ctx.send("⚠️ User is already muted.")
                return
            await member.add_roles(mute_role, reason=reason)
            await ctx.send(f"🔇 {member.mention} has been **muted**.\nReason: {reason}")
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to mute this user.")
        except Exception as e:
            await ctx.send(f"❌ Could not mute: {e}")

    # UNMUTE
    @commands.command(name="unmute")
    async def unmute(self, ctx, member: discord.Member = None):
        # Check if user has manage_roles permission OR administrator
        if not self.has_admin_or_permission(ctx.author, 'manage_roles'):
            await ctx.send("❌ You need Manage Roles permission or Administrator role.")
            return
        
        if not member:
            await ctx.send("❌ Please mention a user to unmute.")
            return
        mute_role = discord.utils.get(ctx.guild.roles, name="Muted")
        if not mute_role or mute_role not in member.roles:
            await ctx.send("❌ User is not muted.")
            return
        try:
            await member.remove_roles(mute_role)
            await ctx.send(f"🔊 {member.mention} has been **unmuted**.")
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to unmute this user.")
        except Exception as e:
            await ctx.send(f"❌ Could not unmute: {e}")

    # TEMP MUTE
    @commands.command(name="tempmute")
    async def tempmute(self, ctx, member: discord.Member = None, duration: int = None, *, reason="No reason provided"):
        # Check if user has manage_roles permission OR administrator
        if not self.has_admin_or_permission(ctx.author, 'manage_roles'):
            await ctx.send("❌ You need Manage Roles permission or Administrator role.")
            return
        
        if not member or not duration:
            await ctx.send("❌ Usage: `/tempmute <user> <duration_seconds> [reason]`")
            return
        mute_role = discord.utils.get(ctx.guild.roles, name="Muted")
        try:
            if not mute_role:
                mute_role = await ctx.guild.create_role(name="Muted")
                for channel in ctx.guild.channels:
                    await channel.set_permissions(mute_role, speak=False, send_messages=False)
            await member.add_roles(mute_role, reason=reason)
            await ctx.send(f"⏳ {member.mention} has been muted for {duration} seconds.\nReason: {reason}")
            await asyncio.sleep(duration)
            if mute_role in member.roles:
                await member.remove_roles(mute_role)
                await ctx.send(f"🔊 {member.mention} has been **auto-unmuted** after {duration} seconds.")
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to tempmute this user.")
        except Exception as e:
            await ctx.send(f"❌ Could not tempmute: {e}")

    # WARN
    @commands.command(name="warn")
    async def warn(self, ctx, member: discord.Member = None, *, reason="No reason provided"):
        # Check if user has manage_messages permission OR administrator
        if not self.has_admin_or_permission(ctx.author, 'manage_messages'):
            await ctx.send("❌ You need Manage Messages permission or Administrator role.")
            return
        
        if not member:
            await ctx.send("❌ Please mention a user to warn.")
            return
        if member.id not in self.user_warnings:
            self.user_warnings[member.id] = []
        self.user_warnings[member.id].append((datetime.utcnow(), reason))
        await ctx.send(f"⚠️ {member.mention} has been **warned**.\nReason: {reason}")

    # INFRACTIONS
    @commands.command(name="infractions")
    async def infractions(self, ctx, member: discord.Member = None):
        if not member:
            await ctx.send("❌ Please mention a user to check infractions.")
            return
        if member.id not in self.user_warnings or not self.user_warnings[member.id]:
            await ctx.send(f"✅ {member.mention} has a clean record.")
        else:
            embed = discord.Embed(
                title=f"⚠️ Infractions for {member.name}",
                color=discord.Color.orange()
            )
            for i, (timestamp, reason) in enumerate(self.user_warnings[member.id], start=1):
                embed.add_field(
                    name=f"#{i} - {timestamp.strftime('%Y-%m-%d %H:%M UTC')}",
                    value=reason,
                    inline=False
                )
            await ctx.send(embed=embed)

    # CLEAR / PURGE
    @commands.command(aliases=["purge"])
    async def clear(self, ctx, amount: int = None):
        # Check if user has manage_messages permission OR administrator
        if not self.has_admin_or_permission(ctx.author, 'manage_messages'):
            await ctx.send("❌ You need Manage Messages permission or Administrator role.")
            return
        
        if amount is None:
            await ctx.send("❌ You must specify the number of messages to delete, e.g., `/clear 10`.")
            return
        try:
            await ctx.channel.purge(limit=amount + 1)
            msg = await ctx.send(f"🧹 Deleted {amount} messages.")
            await asyncio.sleep(2)
            await msg.delete()
        except Exception as e:
            await ctx.send(f"❌ Could not delete messages: {e}")

    # ROLE INFO
    @commands.command(name="role-info")
    async def role_info(self, ctx, role: discord.Role = None):
        if not role:
            await ctx.send("❌ Please mention a role.")
            return
        try:
            embed = discord.Embed(title=f"🎭 Role Info: {role.name}", color=role.color)
            embed.add_field(name="ID", value=role.id)
            embed.add_field(name="Members", value=len(role.members))
            embed.add_field(name="Created", value=role.created_at.strftime("%Y-%m-%d"))
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"❌ Could not fetch role info: {e}")

    # USER INFO
    @commands.command(name="user-info")
    async def user_info(self, ctx, member: discord.Member = None):
        if not member:
            await ctx.send("❌ Please mention a user.")
            return
        try:
            join_date = member.joined_at.strftime("%Y-%m-%d")
            embed = discord.Embed(
                title=f"👤 User Info: {member.display_name}",
                color=discord.Color.blue()
            )
            embed.add_field(name="Joined Server", value=join_date)
            embed.add_field(name="Account Created", value=member.created_at.strftime("%Y-%m-%d"))
            embed.add_field(name="Roles", value=", ".join([r.name for r in member.roles if r.name != '@everyone']) or "None")
            embed.set_thumbnail(url=member.display_avatar)
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"❌ Could not fetch user info: {e}")

    # SERVER INFO
    @commands.command(name="server-info")
    async def server_info(self, ctx):
        try:
            guild = ctx.guild
            embed = discord.Embed(
                title=f"🏰 Server Info: {guild.name}",
                color=discord.Color.green()
            )
            embed.add_field(name="Owner", value=guild.owner.mention)
            embed.add_field(name="Members", value=guild.member_count)
            embed.add_field(name="Created", value=guild.created_at.strftime("%Y-%m-%d"))
            if guild.icon:
                embed.set_thumbnail(url=guild.icon.url)
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"❌ Could not fetch server info: {e}")

async def setup(bot):
    await bot.add_cog(Moderation(bot))
