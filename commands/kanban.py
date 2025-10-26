import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import logging
from typing import Optional, Literal

logger = logging.getLogger(__name__)  # FIXED: Changed _name_ to __name__

class KanbanBoard(commands.Cog):
    """Visual Kanban board for task management"""
    
    def __init__(self, bot, get_db_connection_func):  # FIXED: Changed _init_ to __init__
        self.bot = bot
        self.get_db_connection = get_db_connection_func
        self.init_db_tables()

    def init_db_tables(self):
        """Initialize Kanban-related tables"""
        try:
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        # Kanban columns table
                        cur.execute("""
                            CREATE TABLE IF NOT EXISTS kanban_columns (
                                id SERIAL PRIMARY KEY,
                                guild_id BIGINT NOT NULL,
                                column_name TEXT NOT NULL,
                                position INT NOT NULL,
                                is_default BOOLEAN DEFAULT FALSE,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                UNIQUE(guild_id, column_name)
                            )
                        """)
                        
                        # Kanban swimlanes table
                        cur.execute("""
                            CREATE TABLE IF NOT EXISTS kanban_swimlanes (
                                id SERIAL PRIMARY KEY,
                                guild_id BIGINT NOT NULL,
                                swimlane_name TEXT NOT NULL,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                UNIQUE(guild_id, swimlane_name)
                            )
                        """)
                        
                        # Add kanban_column to team_tasks if it doesn't exist
                        cur.execute("""
                            DO $$ 
                            BEGIN
                                IF NOT EXISTS (
                                    SELECT 1 FROM information_schema.columns 
                                    WHERE table_name='team_tasks' AND column_name='kanban_column'
                                ) THEN
                                    ALTER TABLE team_tasks ADD COLUMN kanban_column TEXT DEFAULT 'todo';
                                END IF;
                            END $$;
                        """)
                        
                        # Add swimlane column to team_tasks
                        cur.execute("""
                            DO $$ 
                            BEGIN
                                IF NOT EXISTS (
                                    SELECT 1 FROM information_schema.columns 
                                    WHERE table_name='team_tasks' AND column_name='swimlane'
                                ) THEN
                                    ALTER TABLE team_tasks ADD COLUMN swimlane TEXT;
                                END IF;
                            END $$;
                        """)
                        
                        conn.commit()
                    logger.info("✅ Kanban tables initialized")
                else:
                    logger.warning("⚠️ Database connection not available")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Kanban tables: {e}")
            import traceback
            traceback.print_exc()

    def get_default_columns(self, guild_id):
        """Get columns for a guild (default or custom)"""
        default_columns = ["backlog", "todo", "in_progress", "review", "done", "blocked"]
        
        try:
            with self.get_db_connection() as conn:
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            SELECT column_name FROM kanban_columns 
                            WHERE guild_id = %s 
                            ORDER BY position
                        """, (guild_id,))
                        rows = cur.fetchall()
                        
                        if rows:
                            return [row[0] for row in rows]
        except Exception as e:
            logger.error(f"Error getting columns: {e}")
        
        return default_columns

    @commands.hybrid_group(name="kanban", description="Kanban board management", invoke_without_command=True)
    async def kanban(self, ctx: commands.Context):
        """Kanban commands help"""
        embed = discord.Embed(
            title="📋 Kanban Board Commands",
            description=(
                "**/kanban view** - Display Kanban board\n"
                "**/kanban move <task_id> <column>** - Move task to column\n"
                "**/kanban columns** - List all columns\n"
                "**/kanban add_column <name>** - Add custom column\n"
                "**/kanban remove_column <name>** - Remove custom column\n"
                "**/kanban clear <column>** - Clear all tasks from column\n"
                "**/kanban swimlane <action> <name>** - Manage swimlanes"
            ),
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)

    @kanban.command(name="view", description="Display Kanban board")
    @app_commands.describe(view_type="Type of view (team/personal)")
    async def kanban_view(self, ctx: commands.Context, view_type: Literal["team", "personal"] = "team"):
        """Display Kanban board"""
        try:
            columns = self.get_default_columns(ctx.guild.id)
            
            with self.get_db_connection() as conn:
                if not conn:
                    await ctx.send("❌ Database connection unavailable.", ephemeral=True)
                    return
                
                with conn.cursor() as cur:
                    if view_type == "personal":
                        # Show only user's assigned tasks
                        cur.execute("""
                            SELECT task_id, title, kanban_column, priority, status
                            FROM team_tasks 
                            WHERE guild_id = %s AND assignee_id = %s
                            ORDER BY CASE priority 
                                WHEN 'urgent' THEN 1 
                                WHEN 'high' THEN 2 
                                WHEN 'medium' THEN 3 
                                WHEN 'low' THEN 4 
                            END
                        """, (ctx.guild.id, ctx.author.id))
                    else:
                        # Show all team tasks
                        cur.execute("""
                            SELECT task_id, title, kanban_column, priority, status, assignee_id
                            FROM team_tasks 
                            WHERE guild_id = %s
                            ORDER BY CASE priority 
                                WHEN 'urgent' THEN 1 
                                WHEN 'high' THEN 2 
                                WHEN 'medium' THEN 3 
                                WHEN 'low' THEN 4 
                            END
                        """, (ctx.guild.id,))
                    
                    tasks = cur.fetchall()
            
            # Organize tasks by column
            columns_data = {col: [] for col in columns}
            
            for task in tasks:
                task_id, title, column, priority, status = task[0], task[1], task[2], task[3], task[4]
                assignee_id = task[5] if len(task) > 5 else None
                
                # Ensure column exists
                if column not in columns_data:
                    column = "todo"  # Default fallback
                
                # Format task info
                priority_emoji = {
                    'urgent': '🔴',
                    'high': '🟠',
                    'medium': '🟡',
                    'low': '🟢'
                }.get(priority, '⚪')
                
                task_info = f"{priority_emoji} {task_id} {title[:30]}"
                
                if assignee_id and view_type == "team":
                    user = self.bot.get_user(assignee_id)
                    if user:
                        task_info += f" (@{user.name})"
                
                columns_data[column].append(task_info)
            
            # Create embed
            embed = discord.Embed(
                title=f"📋 {'Personal' if view_type == 'personal' else 'Team'} Kanban Board",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )
            
            # Add columns as fields
            for column in columns:
                tasks_list = columns_data[column]
                value = "\n".join(tasks_list[:5]) if tasks_list else "No tasks"
                
                if len(tasks_list) > 5:
                    value += f"\n*...and {len(tasks_list) - 5} more*"
                
                embed.add_field(
                    name=f"{column.upper().replace('_', ' ')} ({len(tasks_list)})",
                    value=value,
                    inline=True
                )
            
            embed.set_footer(text=f"Requested by {ctx.author.display_name}")
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"kanban_view error: {e}")
            import traceback
            traceback.print_exc()
            await ctx.send("❌ Failed to display Kanban board.", ephemeral=True)

    @kanban.command(name="move", description="Move task to different column")
    @app_commands.describe(
        task_id="Task ID to move",
        column="Destination column"
    )
    async def kanban_move(self, ctx: commands.Context, task_id: str, column: str):
        """Move task to column"""
        try:
            column = column.lower().replace(" ", "_")
            columns = self.get_default_columns(ctx.guild.id)
            
            if column not in columns:
                await ctx.send(
                    f"❌ Invalid column. Available: {', '.join(columns)}",
                    ephemeral=True
                )
                return
            
            with self.get_db_connection() as conn:
                if not conn:
                    await ctx.send("❌ Database connection unavailable.", ephemeral=True)
                    return
                
                with conn.cursor() as cur:
                    # Update task column
                    cur.execute("""
                        UPDATE team_tasks 
                        SET kanban_column = %s
                        WHERE task_id = %s AND guild_id = %s
                        RETURNING title
                    """, (column, task_id, ctx.guild.id))
                    
                    result = cur.fetchone()
                    
                    if not result:
                        await ctx.send(f"❌ Task {task_id} not found.", ephemeral=True)
                        return
                    
                    conn.commit()
            
            embed = discord.Embed(
                title="✅ Task Moved",
                description=f"**{result[0]}**\n\nMoved to: **{column.upper().replace('_', ' ')}**",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"kanban_move error: {e}")
            await ctx.send("❌ Failed to move task.", ephemeral=True)

    @kanban.command(name="columns", description="List all Kanban columns")
    async def kanban_columns(self, ctx: commands.Context):
        """List columns"""
        try:
            columns = self.get_default_columns(ctx.guild.id)
            
            embed = discord.Embed(
                title="📋 Kanban Columns",
                description="\n".join([f"{i+1}. {col.upper().replace('_', ' ')}" for i, col in enumerate(columns)]),
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"kanban_columns error: {e}")
            await ctx.send("❌ Failed to list columns.", ephemeral=True)

    @kanban.command(name="add_column", description="Add custom Kanban column")
    @app_commands.describe(name="Column name")
    async def kanban_add_column(self, ctx: commands.Context, *, name: str):
        """Add custom column"""
        try:
            column_name = name.lower().replace(" ", "_")
            
            with self.get_db_connection() as conn:
                if not conn:
                    await ctx.send("❌ Database connection unavailable.", ephemeral=True)
                    return
                
                with conn.cursor() as cur:
                    # Get max position
                    cur.execute("""
                        SELECT COALESCE(MAX(position), 0) + 1 
                        FROM kanban_columns 
                        WHERE guild_id = %s
                    """, (ctx.guild.id,))
                    position = cur.fetchone()[0]
                    
                    # Insert column
                    cur.execute("""
                        INSERT INTO kanban_columns (guild_id, column_name, position)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (guild_id, column_name) DO NOTHING
                        RETURNING column_name
                    """, (ctx.guild.id, column_name, position))
                    
                    result = cur.fetchone()
                    
                    if not result:
                        await ctx.send(f"❌ Column **{name}** already exists.", ephemeral=True)
                        return
                    
                    conn.commit()
            
            await ctx.send(f"✅ Added column: **{name.upper()}**")
            
        except Exception as e:
            logger.error(f"kanban_add_column error: {e}")
            await ctx.send("❌ Failed to add column.", ephemeral=True)

    @kanban.command(name="remove_column", description="Remove custom Kanban column")
    @app_commands.describe(name="Column name to remove")
    async def kanban_remove_column(self, ctx: commands.Context, *, name: str):
        """Remove custom column"""
        try:
            column_name = name.lower().replace(" ", "_")
            
            # Don't allow removing default columns
            default_columns = ["backlog", "todo", "in_progress", "review", "done", "blocked"]
            if column_name in default_columns:
                await ctx.send("❌ Cannot remove default columns.", ephemeral=True)
                return
            
            with self.get_db_connection() as conn:
                if not conn:
                    await ctx.send("❌ Database connection unavailable.", ephemeral=True)
                    return
                
                with conn.cursor() as cur:
                    # Check if any tasks are in this column
                    cur.execute("""
                        SELECT COUNT(*) FROM team_tasks 
                        WHERE guild_id = %s AND kanban_column = %s
                    """, (ctx.guild.id, column_name))
                    
                    count = cur.fetchone()[0]
                    
                    if count > 0:
                        await ctx.send(
                            f"❌ Cannot remove column with **{count}** tasks. Move them first.",
                            ephemeral=True
                        )
                        return
                    
                    # Delete column
                    cur.execute("""
                        DELETE FROM kanban_columns 
                        WHERE guild_id = %s AND column_name = %s
                        RETURNING column_name
                    """, (ctx.guild.id, column_name))
                    
                    result = cur.fetchone()
                    
                    if not result:
                        await ctx.send(f"❌ Column **{name}** not found.", ephemeral=True)
                        return
                    
                    conn.commit()
            
            await ctx.send(f"✅ Removed column: **{name.upper()}**")
            
        except Exception as e:
            logger.error(f"kanban_remove_column error: {e}")
            await ctx.send("❌ Failed to remove column.", ephemeral=True)

    @kanban.command(name="clear", description="Clear all tasks from a column")
    @app_commands.describe(column="Column to clear")
    async def kanban_clear(self, ctx: commands.Context, column: str):
        """Clear column"""
        try:
            column = column.lower().replace(" ", "_")
            columns = self.get_default_columns(ctx.guild.id)
            
            if column not in columns:
                await ctx.send(
                    f"❌ Invalid column. Available: {', '.join(columns)}",
                    ephemeral=True
                )
                return
            
            with self.get_db_connection() as conn:
                if not conn:
                    await ctx.send("❌ Database connection unavailable.", ephemeral=True)
                    return
                
                with conn.cursor() as cur:
                    # Move tasks to 'done' or delete based on column
                    cur.execute("""
                        UPDATE team_tasks 
                        SET kanban_column = 'done', status = 'Done'
                        WHERE guild_id = %s AND kanban_column = %s
                        RETURNING task_id
                    """, (ctx.guild.id, column))
                    
                    cleared = cur.fetchall()
                    conn.commit()
            
            await ctx.send(f"🧹 Cleared **{len(cleared)}** tasks from **{column.upper().replace('_', ' ')}**")
            
        except Exception as e:
            logger.error(f"kanban_clear error: {e}")
            await ctx.send("❌ Failed to clear column.", ephemeral=True)

    @kanban.command(name="swimlane", description="Manage board swimlanes")
    @app_commands.describe(
        action="Action (create/delete/list)",
        name="Swimlane name"
    )
    async def kanban_swimlane(self, ctx: commands.Context, action: Literal["create", "delete", "list"], name: Optional[str] = None):
        """Manage swimlanes"""
        try:
            action = action.lower()
            
            if action == "list":
                with self.get_db_connection() as conn:
                    if not conn:
                        await ctx.send("❌ Database connection unavailable.", ephemeral=True)
                        return
                    
                    with conn.cursor() as cur:
                        cur.execute("""
                            SELECT swimlane_name FROM kanban_swimlanes 
                            WHERE guild_id = %s
                        """, (ctx.guild.id,))
                        swimlanes = cur.fetchall()
                
                if not swimlanes:
                    await ctx.send("📋 No swimlanes created yet.")
                    return
                
                embed = discord.Embed(
                    title="🏊 Swimlanes",
                    description="\n".join([f"• {sw[0]}" for sw in swimlanes]),
                    color=discord.Color.blue()
                )
                await ctx.send(embed=embed)
                return
            
            if not name:
                await ctx.send("❌ Please provide a swimlane name.", ephemeral=True)
                return
            
            swimlane_name = name.lower().replace(" ", "_")
            
            with self.get_db_connection() as conn:
                if not conn:
                    await ctx.send("❌ Database connection unavailable.", ephemeral=True)
                    return
                
                with conn.cursor() as cur:
                    if action == "create":
                        cur.execute("""
                            INSERT INTO kanban_swimlanes (guild_id, swimlane_name)
                            VALUES (%s, %s)
                            ON CONFLICT (guild_id, swimlane_name) DO NOTHING
                            RETURNING swimlane_name
                        """, (ctx.guild.id, swimlane_name))
                        
                        result = cur.fetchone()
                        
                        if not result:
                            await ctx.send(f"❌ Swimlane **{name}** already exists.", ephemeral=True)
                            return
                        
                        conn.commit()
                        await ctx.send(f"✅ Created swimlane: **{name}**")
                        
                    elif action == "delete":
                        cur.execute("""
                            DELETE FROM kanban_swimlanes 
                            WHERE guild_id = %s AND swimlane_name = %s
                            RETURNING swimlane_name
                        """, (ctx.guild.id, swimlane_name))
                        
                        result = cur.fetchone()
                        
                        if not result:
                            await ctx.send(f"❌ Swimlane **{name}** not found.", ephemeral=True)
                            return
                        
                        conn.commit()
                        await ctx.send(f"🗑️ Deleted swimlane: **{name}**")
            
        except Exception as e:
            logger.error(f"kanban_swimlane error: {e}")
            await ctx.send("❌ Failed to manage swimlane.", ephemeral=True)

    @commands.hybrid_group(name="board", description="Alternative Kanban board commands", invoke_without_command=True)
    async def board(self, ctx: commands.Context):
        """Board commands help"""
        embed = discord.Embed(
            title="📋 Board Commands",
            description=(
                "**/board view [type]** - Display board\n"
                "**/board move <task_id> <column>** - Move task\n"
                "**/board filter <criteria>** - Filter board view\n"
                "**/board archive** - Archive completed tasks"
            ),
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)

    @board.command(name="view", description="Display board")
    @app_commands.describe(view_type="Board type")
    async def board_view(self, ctx: commands.Context, view_type: Literal["team", "personal"] = "team"):
        """Display board - alias for kanban view"""
        await self.kanban_view.callback(self, ctx, view_type)

    @board.command(name="move", description="Move task between columns")
    @app_commands.describe(task_id="Task ID", column="Target column")
    async def board_move(self, ctx: commands.Context, task_id: str, column: str):
        """Move task - alias for kanban move"""
        await self.kanban_move.callback(self, ctx, task_id, column)

    @board.command(name="filter", description="Filter board view")
    @app_commands.describe(
        filter_type="Filter type",
        value="Filter value"
    )
    async def board_filter(self, ctx: commands.Context, filter_type: Literal["status", "priority", "assignee"], value: str):
        """Filter board"""
        try:
            with self.get_db_connection() as conn:
                if not conn:
                    await ctx.send("❌ Database connection unavailable.", ephemeral=True)
                    return
                
                with conn.cursor() as cur:
                    if filter_type == "status":
                        cur.execute("""
                            SELECT task_id, title, kanban_column, priority, status, assignee_id
                            FROM team_tasks 
                            WHERE guild_id = %s AND status ILIKE %s
                            ORDER BY CASE priority 
                                WHEN 'urgent' THEN 1 
                                WHEN 'high' THEN 2 
                                WHEN 'medium' THEN 3 
                                WHEN 'low' THEN 4 
                            END
                        """, (ctx.guild.id, f'%{value}%'))
                    elif filter_type == "priority":
                        cur.execute("""
                            SELECT task_id, title, kanban_column, priority, status, assignee_id
                            FROM team_tasks 
                            WHERE guild_id = %s AND priority ILIKE %s
                            ORDER BY created_at DESC
                        """, (ctx.guild.id, f'%{value}%'))
                    elif filter_type == "assignee":
                        # Try to find user by name
                        user = discord.utils.find(lambda m: value.lower() in m.name.lower(), ctx.guild.members)
                        user_id = user.id if user else None
                        
                        cur.execute("""
                            SELECT task_id, title, kanban_column, priority, status, assignee_id
                            FROM team_tasks 
                            WHERE guild_id = %s AND assignee_id = %s
                            ORDER BY CASE priority 
                                WHEN 'urgent' THEN 1 
                                WHEN 'high' THEN 2 
                                WHEN 'medium' THEN 3 
                                WHEN 'low' THEN 4 
                            END
                        """, (ctx.guild.id, user_id))
                    
                    tasks = cur.fetchall()
            
            if not tasks:
                await ctx.send(f"📋 No tasks found matching filter: **{filter_type}={value}**")
                return
            
            embed = discord.Embed(
                title=f"📋 Filtered Board: {filter_type.title()}={value}",
                color=discord.Color.blue()
            )
            
            for task in tasks[:15]:
                task_id, title, column, priority, status, assignee_id = task
                
                priority_emoji = {
                    'urgent': '🔴',
                    'high': '🟠',
                    'medium': '🟡',
                    'low': '🟢'
                }.get(priority, '⚪')
                
                assignee = ""
                if assignee_id:
                    user = self.bot.get_user(assignee_id)
                    if user:
                        assignee = f" → {user.mention}"
                
                embed.add_field(
                    name=f"{priority_emoji} {task_id} - {column.upper()}",
                    value=f"{title}\n{status}{assignee}",
                    inline=False
                )
            
            if len(tasks) > 15:
                embed.set_footer(text=f"Showing 15 of {len(tasks)} tasks")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"board_filter error: {e}")
            await ctx.send("❌ Failed to filter board.", ephemeral=True)

    @board.command(name="archive", description="Archive completed tasks")
    async def board_archive(self, ctx: commands.Context):
        """Archive completed tasks"""
        try:
            with self.get_db_connection() as conn:
                if not conn:
                    await ctx.send("❌ Database connection unavailable.", ephemeral=True)
                    return
                
                with conn.cursor() as cur:
                    # Move done tasks to archived status
                    cur.execute("""
                        UPDATE team_tasks 
                        SET kanban_column = 'archived'
                        WHERE guild_id = %s AND status = 'Done' AND kanban_column = 'done'
                        RETURNING task_id
                    """, (ctx.guild.id,))
                    
                    archived = cur.fetchall()
                    conn.commit()
            
            await ctx.send(f"📦 Archived **{len(archived)}** completed tasks.")
            
        except Exception as e:
            logger.error(f"board_archive error: {e}")
            await ctx.send("❌ Failed to archive tasks.", ephemeral=True)


async def setup(bot: commands.Bot):
    """Setup function for the cog"""
    try:
        get_db_connection_func = getattr(bot, "get_db_connection", None)
        if not get_db_connection_func:
            logger.error("❌ get_db_connection not found on bot instance")
            return
        
        await bot.add_cog(KanbanBoard(bot, get_db_connection_func))
        logger.info("✅ KanbanBoard cog loaded successfully")
    except Exception as e:
        logger.error(f"❌ Failed to setup KanbanBoard cog: {e}")
        import traceback
        traceback.print_exc()
