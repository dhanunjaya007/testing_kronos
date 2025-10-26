import discord
from discord.ext import commands
from discord import app_commands
import logging

logger = logging.getLogger(__name__)

class CustomHelp(commands.Cog):
    """Comprehensive help system for all bot commands"""
    
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="help", description="Show help menu for commands")
    @app_commands.describe(category="Command category to view")
    async def help(self, ctx: commands.Context, category: str = None):
        """Display help information"""
        
        help_data = {
            "task management": {
                "title": "📋 Task Management Commands",
                "commands": {
                    "/task create <title> <description>": "Create a new team task",
                    "/task list [filter]": "View all tasks (filter by status, assignee, priority)",
                    "/task view <task_id>": "View detailed info about a specific task",
                    "/task assign <task_id> <user>": "Assign task to a team member",
                    "/task complete <task_id>": "Mark task as completed",
                    "/task delete <task_id>": "Delete a task"
                },
            },
            "kanban board": {
                "title": "📊 Kanban Board Commands",
                "commands": {
                    "/kanban view [type]": "Display Kanban board (team/personal)",
                    "/kanban move <task_id> <column>": "Move task to different column",
                    "/kanban columns": "List all available columns",
                    "/kanban add_column <name>": "Add custom Kanban column",
                    "/kanban remove_column <name>": "Remove custom column",
                    "/kanban clear <column>": "Clear all tasks from a column",
                    "/kanban swimlane <action> <name>": "Manage swimlanes (create/delete/list)",
                    "/board view [type]": "Alternative board view command",
                    "/board filter <type> <value>": "Filter board by status/priority/assignee",
                    "/board archive": "Archive completed tasks"
                }
            },
            "personal tasks": {
                "title": "✅ Personal Tasks Commands",
                "commands": {
                    "/personal create <title>": "Create a personal task",
                    "/personal list": "View your personal tasks",
                    "/personal complete <task_id>": "Complete a personal task",
                    "/personal delete <task_id>": "Delete a personal task"
                }
            },
            "milestones": {
                "title": "🎯 Team Milestones Commands",
                "commands": {
                    "/milestone create <title> <deadline>": "Create a team milestone",
                    "/milestone list": "View all team milestones",
                    "/milestone complete <milestone_id>": "Mark milestone as achieved",
                    "/milestone progress <milestone_id> <percent>": "Update milestone progress"
                }
            },
            "reminders": {
                "title": "⏰ Reminder Commands",
                "commands": {
                    "/reminder set <time> <message>": "Set a one-time reminder",
                    "/reminder recurring <frequency> <time> <msg>": "Set recurring reminder",
                    "/reminder list": "View all active reminders",
                    "/reminder cancel <reminder_id>": "Cancel a reminder",
                    "/reminder clear": "Clear all your reminders"
                }
            },
            "time tracking": {
                "title": "⏱️ Time Tracking Commands",
                "commands": {
                    "/countdown_create <name> <end_time>": "Create a countdown timer",
                    "/countdown_list": "View all active countdowns",
                    "/countdown_delete <countdown_id>": "Delete a countdown",
                    "/timer_start <duration> [message]": "Start a timer (e.g., 25m)",
                    "/timer_stop": "Stop your active timer"
                }
            },
            "meetings": {
                "title": "📅 Meeting & Event Commands",
                "commands": {
                    "/meeting create <title> <date> <time>": "Schedule a meeting",
                    "/meeting list [filter]": "View scheduled meetings",
                    "/meeting rsvp <meeting_id> <response>": "RSVP to a meeting (yes/no/maybe)",
                    "/meeting cancel <meeting_id>": "Cancel a meeting",
                    "/meeting agenda <meeting_id> <agenda>": "Add or update agenda",
                    "/meeting notes <meeting_id> <notes>": "Add meeting notes",
                    "/event create <title> <date> <desc>": "Create an event",
                    "/event list": "View upcoming events"
                }
            },
            "code editor": {
                "title": "💻 Code Editor Integration",
                "commands": {
                    "/code_status [user]": "View current coding status",
                    "/code_now": "See who's currently coding",
                    "/code_stats [user]": "View coding statistics",
                    "/code_sessions [user] [days]": "View recent coding sessions",
                    "/code_languages [user]": "View language breakdown",
                    "/setup_editor": "Interactive editor setup guide",
                    "/setup_vscode": "VS Code extension setup",
                    "/setup_pycharm": "PyCharm plugin setup",
                    "/setup_intellij": "IntelliJ IDEA setup",
                    "/setup_webstorm": "WebStorm setup"
                }
            },
            "gamification": {
                "title": "🎮 Gamification & XP System",
                "commands": {
                    "/xp_view [user]": "View XP and level",
                    "/xp_leaderboard": "Show XP leaderboard",
                    "/level_info": "View level requirements and rewards",
                    "/badge_list [user]": "View earned badges",
                    "/challenge_create <title> <desc> <xp>": "Create a coding challenge",
                    "/challenge_list": "View active challenges",
                    "/challenge_complete <challenge_id>": "Submit challenge completion",
                    "/streak_view [user]": "View coding streak",
                    "/kudos <user>": "Give kudos points",
                    "/kudos_leaderboard": "View kudos leaderboard"
                }
            },
            "celebration": {
                "title": "🎉 Celebration & Morale",
                "commands": {
                    "/celebrate <user> [reason] [type]": "Celebrate team member achievement",
                    "/shoutout <user> <message>": "Give a shoutout",
                    "/morale [user]": "View team morale statistics",
                    "/leaderboard [period]": "View morale leaderboard"
                }
            },
            "productivity": {
                "title": "⚡ Focus & Productivity",
                "commands": {
                    "/focus start <duration> [type]": "Start focus session",
                    "/focus end": "End focus session",
                    "/focus stats [user]": "View focus statistics",
                    "/pomodoro start [duration]": "Start Pomodoro timer (25min default)",
                    "/pomodoro break [duration]": "Start break timer",
                    "/pomodoro end": "End Pomodoro session",
                    "/dnd start <duration> [reason]": "Enable Do Not Disturb mode",
                    "/dnd end": "Disable DND mode"
                }
            },
            "reports": {
                "title": "📊 Daily and Weekly Reports",
                "commands": {
                    "/report_daily": "Generate today's activity report",
                    "/report_weekly": "Generate this week's summary report",
                    "/report_personal [period]": "Generate your personal activity report",
                    "/report_team [period]": "Generate team-wide report",
                    "/report_schedule <frequency> <channel>": "Schedule automatic reports"
                }
            },
            "progress": {
                "title": "📈 Progress Tracking & Analytics",
                "commands": {
                    "/progress_daily": "View today's team progress",
                    "/progress_weekly": "View weekly team summary",
                    "/progress_milestone <milestone_id>": "Check milestone progress",
                    "/progress_user <user>": "View user progress",
                    "/blockers_add <description>": "Report a blocker",
                    "/blockers_list": "List active blockers",
                    "/blockers_resolve <blocker_id>": "Resolve a blocker"
                }
            },
            "collaboration": {
                "title": "👥 Team Collaboration & Notifications",
                "commands": {
                    "/notify_task <task_id> <user> [msg]": "Notify someone about a task",
                    "/notify_standup <time>": "Schedule daily standup reminder",
                    "/notify_settings": "Configure notification preferences",
                    "/notify_mute <type>": "Mute specific notification types",
                    "/notify_unmute <type>": "Unmute notifications",
                    "/status_set <status_message>": "Set your work status",
                    "/status_team": "View all team members' statuses",
                    "/review_request <task_id> <reviewer>": "Request code/task review",
                    "/review_complete <task_id>": "Mark review as done",
                    "/subscribe <event_type>": "Subscribe to event notifications",
                    "/unsubscribe <event_type>": "Unsubscribe from events"
                }
            },
            "github": {
                "title": "🐙 Git/GitHub Integration",
                "commands": {
                    "/setupgit": "Setup GitHub webhook integration (Admin only)",
                    "/creategit": "Create a 'git' channel (Admin only)",
                    "/testgit": "Test git channel configuration"
                }
            },
            "ai": {
                "title": "🤖 AI Assistant",
                "commands": {
                    "/chat <prompt>": "Chat with AI assistant",
                    "/models": "List available AI models",
                    "/reset": "Reset your conversation history"
                }
            },
            "moderation": {
                "title": "🛡️ Moderation Commands",
                "commands": {
                    "/ban <user> [reason]": "Ban a user",
                    "/unban <user>": "Unban a user",
                    "/kick <user> [reason]": "Kick a user",
                    "/mute <user> [reason]": "Mute a user",
                    "/unmute <user>": "Unmute a user",
                    "/tempmute <user> <seconds> [reason]": "Temporarily mute a user",
                    "/warn <user> [reason]": "Warn a user",
                    "/infractions <user>": "View user infractions",
                    "/clear <amount>": "Delete messages (also /purge)",
                    "/role-info <role>": "Get role information",
                    "/user-info <user>": "Get user information",
                    "/server-info": "Get server information"
                }
            },
            "utility": {
                "title": "🔧 Utility Commands",
                "commands": {
                    "/hello": "Say hello",
                    "/ping": "Check bot latency",
                    "/serverinfo": "Get server information",
                    "/dbstatus": "Check database connection status",
                    "/help [category]": "Show this help menu"
                }
            }
        }

        if not category:
            # Show all categories
            embed = discord.Embed(
                title="📚 Kronos Bot - Help Menu",
                description="Use `/help <category>` to view specific commands\n\n**Available Categories:**",
                color=discord.Color.blurple()
            )
            
            # Group categories for better display
            categories_list = []
            for cat, data in help_data.items():
                categories_list.append(f"• `{cat}` - {data['title']}")
            
            # Split into two columns
            mid = len(categories_list) // 2
            embed.add_field(
                name="📋 Categories (Part 1)",
                value="\n".join(categories_list[:mid]),
                inline=True
            )
            embed.add_field(
                name="📋 Categories (Part 2)",
                value="\n".join(categories_list[mid:]),
                inline=True
            )
            
            embed.set_footer(text="Example: /help task management")
            await ctx.send(embed=embed)
            return

        # Show specific category
        category = category.lower()
        if category not in help_data:
            # Try to find a close match
            suggestions = [cat for cat in help_data.keys() if category in cat or cat in category]
            if suggestions:
                await ctx.send(
                    f"❌ Unknown category: `{category}`\n💡 Did you mean: `{suggestions[0]}`?",
                    ephemeral=True
                )
            else:
                await ctx.send(
                    f"❌ Unknown category: `{category}`\nUse `/help` to see all categories.",
                    ephemeral=True
                )
            return

        embed = discord.Embed(
            title=help_data[category]["title"],
            color=discord.Color.blurple()
        )
        
        for cmd, desc in help_data[category]["commands"].items():
            embed.add_field(name=cmd, value=desc, inline=False)
        
        embed.set_footer(text="Use /help to see all categories")
        await ctx.send(embed=embed)


async def setup(bot):
    """Setup function for the cog"""
    try:
        await bot.add_cog(CustomHelp(bot))
        logger.info("✅ CustomHelp cog loaded successfully")
    except Exception as e:
        logger.error(f"❌ Failed to setup CustomHelp cog: {e}")
        import traceback
        traceback.print_exc()
