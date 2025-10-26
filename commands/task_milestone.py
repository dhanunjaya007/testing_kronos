import discord
from discord.ext import commands
from discord import app_commands
import logging
from typing import Optional, Literal
from datetime import datetime

logger = logging.getLogger(__name__)

class Tasks(commands.Cog):
    def __init__(self, bot, get_db_connection_func):
        self.bot = bot
        self.get_db_connection = get_db_connection_func
        self.init_db_tables()

    def init_db_tables(self):
        """Initialize task management tables"""
        try:
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        # Team tasks table
                        cur.execute("""
                            CREATE TABLE IF NOT EXISTS team_tasks (
                                id SERIAL PRIMARY KEY,
                                task_id TEXT NOT NULL UNIQUE,
                                title TEXT NOT NULL,
                                description TEXT,
                                assignee_id BIGINT,
                                creator_id BIGINT NOT NULL,
                                deadline DATE,
                                priority TEXT CHECK (priority IN ('low', 'medium', 'high', 'urgent')),
                                status TEXT CHECK (status IN ('To Do', 'In Progress', 'Review', 'Done')),
                                dependency_task_id TEXT,
                                blocked BOOLEAN DEFAULT FALSE,
                                block_reason TEXT,
                                estimated_hours DECIMAL(5,2) DEFAULT 0,
                                time_logged DECIMAL(5,2) DEFAULT 0,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                        """)
                        
                        # Personal tasks table
                        cur.execute("""
                            CREATE TABLE IF NOT EXISTS personal_tasks (
                                id SERIAL PRIMARY KEY,
                                task_id TEXT NOT NULL UNIQUE,
                                user_id BIGINT NOT NULL,
                                title TEXT NOT NULL,
                                description TEXT,
                                deadline DATE,
                                status TEXT CHECK (status IN ('Pending', 'In Progress', 'Completed')),
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                        """)
                        
                        # Team milestones table
                        cur.execute("""
                            CREATE TABLE IF NOT EXISTS milestones (
                                id SERIAL PRIMARY KEY,
                                milestone_id TEXT NOT NULL UNIQUE,
                                title TEXT NOT NULL,
                                description TEXT,
                                deadline DATE,
                                status TEXT CHECK (status IN ('Active', 'Completed', 'Cancelled')),
                                progress INTEGER DEFAULT 0 CHECK (progress >= 0 AND progress <= 100),
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                        """)
                        
                        conn.commit()
            logger.info("✅ Task/Milestone tables initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize task/milestone tables: {e}")

    # ===== CORE TASK MANAGEMENT =====

    @commands.hybrid_group(name="task", description="Manage team tasks", invoke_without_command=True)
    async def task(self, ctx: commands.Context):
        """Task commands help"""
        embed = discord.Embed(
            title="📋 Task Commands",
            description=(
                "**/task create <title> <description>** - Create a task\n"
                "**/task list [filter]** - List tasks\n"
                "**/task view <id>** - View task details\n"
                "**/task assign <id> <user>** - Assign task\n"
                "**/task update <id> <field> <value>** - Update task\n"
                "**/task complete <id>** - Mark complete\n"
                "**/task delete <id>** - Delete task"
            ),
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)

    @task.command(name="create", description="Create a new team task")
    @app_commands.describe(
        title="Task title",
        description="Task description",
        assignee="User to assign (optional)",
        deadline="Deadline (YYYY-MM-DD)",
        priority="Priority level (low/medium/high/urgent)"
    )
    async def task_create(self, ctx: commands.Context, title: str, *, description: str = None, 
                          assignee: discord.Member = None, deadline: str = None, 
                          priority: Literal["low", "medium", "high", "urgent"] = "medium"):
        """Create a new task"""
        try:
            task_id = f"T{int(datetime.utcnow().timestamp())}"
            
            # Validate deadline if provided
            deadline_date = None
            if deadline:
                try:
                    deadline_date = datetime.strptime(deadline, "%Y-%m-%d").date()
                except ValueError:
                    await ctx.send("❌ Invalid date format. Use YYYY-MM-DD", ephemeral=True)
                    return
            
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO team_tasks (task_id, title, description, assignee_id, creator_id, deadline, priority, status)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, 'To Do')
                        """, (task_id, title, description, assignee.id if assignee else None, 
                              ctx.author.id, deadline_date, priority))
                        conn.commit()
            
            embed = discord.Embed(
                title="✅ Task Created",
                description=f"**Task #{task_id}**\n\n**{title}**",
                color=discord.Color.green()
            )
            embed.add_field(name="Priority", value=priority.title(), inline=True)
            embed.add_field(name="Status", value="To Do", inline=True)
            if assignee:
                embed.add_field(name="Assigned to", value=assignee.mention, inline=False)
            if deadline:
                embed.add_field(name="Deadline", value=deadline, inline=False)
            embed.set_footer(text=f"Created by {ctx.author.display_name}")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"task_create error: {e}")
            await ctx.send("❌ Failed to create task.", ephemeral=True)

    @task.command(name="list", description="List all tasks")
    @app_commands.describe(filter="Filter by status or priority")
    async def task_list(self, ctx: commands.Context, filter: Optional[str] = None):
        """List tasks"""
        try:
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        if filter:
                            cur.execute("""
                                SELECT task_id, title, status, priority, assignee_id 
                                FROM team_tasks 
                                WHERE status ILIKE %s OR priority ILIKE %s
                                ORDER BY CASE priority 
                                    WHEN 'urgent' THEN 1 
                                    WHEN 'high' THEN 2 
                                    WHEN 'medium' THEN 3 
                                    WHEN 'low' THEN 4 
                                END
                            """, (f'%{filter}%', f'%{filter}%'))
                        else:
                            cur.execute("""
                                SELECT task_id, title, status, priority, assignee_id 
                                FROM team_tasks 
                                ORDER BY CASE priority 
                                    WHEN 'urgent' THEN 1 
                                    WHEN 'high' THEN 2 
                                    WHEN 'medium' THEN 3 
                                    WHEN 'low' THEN 4 
                                END
                            """)
                        rows = cur.fetchall()
            
            if not rows:
                await ctx.send("📝 No tasks found.")
                return
            
            embed = discord.Embed(
                title="📋 Tasks List",
                color=discord.Color.blue()
            )
            
            for task_id, title, status, priority, assignee_id in rows[:15]:  # Limit to 15
                assignee = ""
                if assignee_id:
                    user = self.bot.get_user(assignee_id)
                    assignee = f" → {user.mention if user else 'Unknown'}"
                
                embed.add_field(
                    name=f"#{task_id} - {priority.upper()}",
                    value=f"**{title}**\n{status}{assignee}",
                    inline=False
                )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"task_list error: {e}")
            await ctx.send("❌ Failed to list tasks.", ephemeral=True)

    @task.command(name="view", description="View task details")
    @app_commands.describe(task_id="Task ID to view")
    async def task_view(self, ctx: commands.Context, *, task_id: str):
        """View task details"""
        try:
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            SELECT * FROM team_tasks WHERE task_id = %s
                        """, (task_id,))
                        row = cur.fetchone()
            
            if not row:
                await ctx.send("❌ Task not found.", ephemeral=True)
                return
            
            # row: id, task_id, title, description, assignee_id, creator_id, deadline, 
            #      priority, status, dependency_task_id, blocked, block_reason, 
            #      estimated_hours, time_logged, created_at
            
            assignee = "Unassigned"
            if row[4]:  # assignee_id
                user = self.bot.get_user(row[4])
                assignee = user.mention if user else "Unknown"
            
            blocked = "🚫 Blocked" if row[10] else "✅ Active"
            
            embed = discord.Embed(
                title=f"📋 Task #{row[1]}",
                description=row[2] or "*No description*",
                color=discord.Color.green() if not row[10] else discord.Color.red()
            )
            
            embed.add_field(name="Status", value=row[8], inline=True)
            embed.add_field(name="Priority", value=row[7].title(), inline=True)
            embed.add_field(name="Assigned to", value=assignee, inline=False)
            
            if row[5]:  # deadline
                embed.add_field(name="Deadline", value=str(row[5]), inline=False)
            
            if row[9]:  # dependency
                embed.add_field(name="Depends on", value=f"Task #{row[9]}", inline=True)
            
            embed.add_field(name="Blocked", value=blocked, inline=True)
            
            if row[12] > 0 or row[13] > 0:  # estimated or logged hours
                embed.add_field(name="Time", value=f"Est: {row[12]}h | Logged: {row[13]}h", inline=False)
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"task_view error: {e}")
            await ctx.send("❌ Failed to view task.", ephemeral=True)

    @task.command(name="assign", description="Assign task to user")
    @app_commands.describe(task_id="Task ID", user="User to assign")
    async def task_assign(self, ctx: commands.Context, task_id: str, user: discord.Member):
        """Assign task"""
        try:
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            UPDATE team_tasks SET assignee_id = %s WHERE task_id = %s
                        """, (user.id, task_id))
                        conn.commit()
            
            await ctx.send(f"👤 Task #{task_id} assigned to {user.mention}")
            
        except Exception as e:
            logger.error(f"task_assign error: {e}")
            await ctx.send("❌ Failed to assign task.", ephemeral=True)

    @task.command(name="complete", description="Mark task as complete")
    @app_commands.describe(task_id="Task ID")
    async def task_complete(self, ctx: commands.Context, task_id: str):
        """Complete task"""
        try:
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            UPDATE team_tasks SET status = 'Done' WHERE task_id = %s
                        """, (task_id,))
                        conn.commit()
            
            await ctx.send(f"✅ Task #{task_id} marked as completed!")
            
        except Exception as e:
            logger.error(f"task_complete error: {e}")
            await ctx.send("❌ Failed to complete task.", ephemeral=True)

    @task.command(name="delete", description="Delete a task")
    @app_commands.describe(task_id="Task ID")
    async def task_delete(self, ctx: commands.Context, task_id: str):
        """Delete task"""
        try:
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("DELETE FROM team_tasks WHERE task_id = %s", (task_id,))
                        conn.commit()
            
            await ctx.send(f"🗑️ Task #{task_id} deleted.")
            
        except Exception as e:
            logger.error(f"task_delete error: {e}")
            await ctx.send("❌ Failed to delete task.", ephemeral=True)

    # ===== PERSONAL TASKS =====

    @commands.hybrid_group(name="personal", description="Manage personal tasks", invoke_without_command=True)
    async def personal(self, ctx: commands.Context):
        """Personal task commands"""
        embed = discord.Embed(
            title="📝 Personal Tasks",
            description=(
                "**/personal create <title>** - Create task\n"
                "**/personal list** - List your tasks\n"
                "**/personal complete <id>** - Complete task\n"
                "**/personal delete <id>** - Delete task"
            ),
            color=discord.Color.purple()
        )
        await ctx.send(embed=embed)

    @personal.command(name="create", description="Create personal task")
    @app_commands.describe(
        title="Task title",
        description="Task description (optional)",
        deadline="Deadline (YYYY-MM-DD)"
    )
    async def personal_create(self, ctx: commands.Context, title: str, *, description: str = None, deadline: str = None):
        """Create personal task"""
        try:
            task_id = f"P{int(datetime.utcnow().timestamp())}"
            
            deadline_date = None
            if deadline:
                try:
                    deadline_date = datetime.strptime(deadline, "%Y-%m-%d").date()
                except ValueError:
                    await ctx.send("❌ Invalid date format. Use YYYY-MM-DD", ephemeral=True)
                    return
            
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO personal_tasks (task_id, user_id, title, description, deadline, status)
                            VALUES (%s, %s, %s, %s, %s, 'Pending')
                        """, (task_id, ctx.author.id, title, description, deadline_date))
                        conn.commit()
            
            embed = discord.Embed(
                title="✅ Personal Task Created",
                description=f"**{title}**",
                color=discord.Color.green()
            )
            if deadline:
                embed.add_field(name="Deadline", value=deadline, inline=False)
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"personal_create error: {e}")
            await ctx.send("❌ Failed to create task.", ephemeral=True)

    @personal.command(name="list", description="List your personal tasks")
    async def personal_list(self, ctx: commands.Context):
        """List personal tasks"""
        try:
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            SELECT task_id, title, status, deadline 
                            FROM personal_tasks 
                            WHERE user_id = %s
                            ORDER BY created_at DESC
                        """, (ctx.author.id,))
                        rows = cur.fetchall()
            
            if not rows:
                await ctx.send("📝 No personal tasks found.")
                return
            
            embed = discord.Embed(
                title=f"📝 Your Tasks ({len(rows)})",
                color=discord.Color.purple()
            )
            
            for task_id, title, status, deadline in rows[:15]:
                deadline_str = f"\n📅 {deadline}" if deadline else ""
                embed.add_field(
                    name=f"#{task_id} - {status}",
                    value=f"**{title}**{deadline_str}",
                    inline=False
                )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"personal_list error: {e}")
            await ctx.send("❌ Failed to list tasks.", ephemeral=True)

    @personal.command(name="complete", description="Complete personal task")
    @app_commands.describe(task_id="Task ID")
    async def personal_complete(self, ctx: commands.Context, task_id: str):
        """Complete personal task"""
        try:
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            UPDATE personal_tasks 
                            SET status = 'Completed' 
                            WHERE task_id = %s AND user_id = %s
                        """, (task_id, ctx.author.id))
                        conn.commit()
            
            await ctx.send(f"✅ Task #{task_id} marked as completed!")
            
        except Exception as e:
            logger.error(f"personal_complete error: {e}")
            await ctx.send("❌ Failed to complete task.", ephemeral=True)

    @personal.command(name="delete", description="Delete personal task")
    @app_commands.describe(task_id="Task ID")
    async def personal_delete(self, ctx: commands.Context, task_id: str):
        """Delete personal task"""
        try:
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            DELETE FROM personal_tasks 
                            WHERE task_id = %s AND user_id = %s
                        """, (task_id, ctx.author.id))
                        conn.commit()
            
            await ctx.send(f"🗑️ Task #{task_id} deleted.")
            
        except Exception as e:
            logger.error(f"personal_delete error: {e}")
            await ctx.send("❌ Failed to delete task.", ephemeral=True)

    # ===== MILESTONES =====

    @commands.hybrid_group(name="milestone", description="Manage team milestones", invoke_without_command=True)
    async def milestone(self, ctx: commands.Context):
        """Milestone commands"""
        embed = discord.Embed(
            title="🎯 Milestone Commands",
            description=(
                "**/milestone create <title> <deadline>** - Create milestone\n"
                "**/milestone list** - List milestones\n"
                "**/milestone complete <id>** - Complete milestone\n"
                "**/milestone progress <id>** - Update progress"
            ),
            color=discord.Color.gold()
        )
        await ctx.send(embed=embed)

    @milestone.command(name="create", description="Create a milestone")
    @app_commands.describe(
        title="Milestone title",
        description="Description",
        deadline="Deadline (YYYY-MM-DD)"
    )
    async def milestone_create(self, ctx: commands.Context, title: str, deadline: str, *, description: str = None):
        """Create milestone"""
        try:
            milestone_id = f"M{int(datetime.utcnow().timestamp())}"
            
            try:
                deadline_date = datetime.strptime(deadline, "%Y-%m-%d").date()
            except ValueError:
                await ctx.send("❌ Invalid date format. Use YYYY-MM-DD", ephemeral=True)
                return
            
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO milestones (milestone_id, title, description, deadline, status, progress)
                            VALUES (%s, %s, %s, %s, 'Active', 0)
                        """, (milestone_id, title, description, deadline_date))
                        conn.commit()
            
            embed = discord.Embed(
                title="🎯 Milestone Created",
                description=f"**{title}**",
                color=discord.Color.gold()
            )
            embed.add_field(name="Deadline", value=deadline, inline=False)
            embed.add_field(name="Progress", value="0%", inline=True)
            embed.add_field(name="Status", value="Active", inline=True)
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"milestone_create error: {e}")
            await ctx.send("❌ Failed to create milestone.", ephemeral=True)

    @milestone.command(name="list", description="List all milestones")
    async def milestone_list(self, ctx: commands.Context):
        """List milestones"""
        try:
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            SELECT milestone_id, title, status, progress, deadline
                            FROM milestones
                            ORDER BY deadline ASC
                        """)
                        rows = cur.fetchall()
            
            if not rows:
                await ctx.send("📋 No milestones found.")
                return
            
            embed = discord.Embed(
                title="🎯 Milestones",
                color=discord.Color.gold()
            )
            
            for milestone_id, title, status, progress, deadline in rows:
                deadline_str = f" (Due: {deadline})" if deadline else ""
                embed.add_field(
                    name=f"#{milestone_id} - {status}",
                    value=f"**{title}**\n📊 {progress}%{deadline_str}",
                    inline=False
                )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"milestone_list error: {e}")
            await ctx.send("❌ Failed to list milestones.", ephemeral=True)

    @milestone.command(name="complete", description="Mark milestone as complete")
    @app_commands.describe(milestone_id="Milestone ID")
    async def milestone_complete(self, ctx: commands.Context, milestone_id: str):
        """Complete milestone"""
        try:
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            UPDATE milestones 
                            SET status = 'Completed', progress = 100 
                            WHERE milestone_id = %s
                        """, (milestone_id,))
                        conn.commit()
            
            embed = discord.Embed(
                title="🏆 Milestone Achieved!",
                description=f"**#{milestone_id}**",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"milestone_complete error: {e}")
            await ctx.send("❌ Failed to complete milestone.", ephemeral=True)

    @milestone.command(name="progress", description="Update milestone progress")
    @app_commands.describe(milestone_id="Milestone ID", progress="Progress (0-100)")
    async def milestone_progress(self, ctx: commands.Context, milestone_id: str, progress: int):
        """Update milestone progress"""
        try:
            if progress < 0 or progress > 100:
                await ctx.send("❌ Progress must be between 0-100", ephemeral=True)
                return
            
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            UPDATE milestones SET progress = %s WHERE milestone_id = %s
                        """, (progress, milestone_id))
                        conn.commit()
            
            await ctx.send(f"📊 Milestone #{milestone_id} progress: {progress}%")
            
        except Exception as e:
            logger.error(f"milestone_progress error: {e}")
            await ctx.send("❌ Failed to update progress.", ephemeral=True)


async def setup(bot: commands.Bot):
    """Setup function for the cog"""
    get_db_connection_func = getattr(bot, "get_db_connection", None)
    if not get_db_connection_func:
        logger.error("❌ get_db_connection not found on bot instance")
        return
    await bot.add_cog(Tasks(bot, get_db_connection_func))
    logger.info("✅ Tasks/Milestones cog loaded successfully")
