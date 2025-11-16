# 🤖 Kronos - Advanced Discord Team Management Bot

<div align="center">

![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)
![Discord.py](https://img.shields.io/badge/discord.py-2.0%2B-blue)
![Flask](https://img.shields.io/badge/Flask-2.0%2B-green)
![License](https://img.shields.io/badge/license-MIT-green)

**A comprehensive Discord bot designed for team productivity, project management, and collaboration**

[Features](#-features) • [Installation](#-installation) • [Configuration](#-configuration) • [Usage](#-usage) • [Contributing](#-contributing)

</div>

---

## 📖 Overview

Kronos is a feature-rich Discord bot built with Discord.py and Flask that transforms your Discord server into a powerful project management and team collaboration hub. Whether you're managing a development team, coordinating remote work, or organizing community projects, Kronos provides all the tools you need to stay productive and engaged.

### Why Kronos?

- **All-in-One Solution**: Combines task management, time tracking, code editor integration, and team coordination in one bot
- **Developer-Focused**: Automatic coding activity tracking and language statistics for developers
- **Gamification**: Keep your team engaged with XP, levels, badges, and coding challenges
- **Flexible & Extensible**: Built with modularity in mind for easy customization and feature additions
- **Free & Open Source**: Use it as-is or customize it to fit your team's unique workflow

---

## ✨ Features

### 📋 Task & Project Management

**Team Tasks**
- Create, assign, and track team tasks with customizable priorities (Low, Medium, High, Critical)
- Set deadlines and due dates with automatic reminders
- Mark tasks as in-progress, completed, or blocked
- View all team tasks in organized, easy-to-read embeds

**Personal Tasks**
- Manage your individual to-do list separate from team responsibilities
- Quick commands to add, complete, and view personal tasks
- Never lose track of your own work while collaborating with the team

**Milestones & Goals**
- Set major project milestones with target completion dates
- Track progress percentages toward each milestone
- Link tasks to milestones to visualize overall project health
- Celebrate team achievements when milestones are reached

**Task Dependencies**
- Define dependencies between tasks (Task B depends on Task A)
- Prevent tasks from starting until prerequisites are complete
- Visualize the critical path of your project


### 💻 Code Editor Integration

**Automatic Activity Tracking**
- Seamlessly tracks coding sessions from popular editors:
  - Visual Studio Code
  - PyCharm / IntelliJ IDEA
  - Sublime Text
  - Atom
  - And more via Discord Rich Presence

**Language Statistics**
- View detailed breakdowns of coding time by programming language
- Daily, weekly, and monthly statistics
- Leaderboards to see top languages used across your team

**Session History**
- Review your recent coding sessions
- See patterns in your work habits
- Track productive hours and coding streaks

**Setup Guides**
- Interactive setup commands with step-by-step instructions
- Editor-specific configuration guides
- Troubleshooting help for common issues

### ⏰ Time Management

**Reminders**
- Create one-time reminders for important deadlines
- Set recurring reminders (daily, weekly, monthly)
- Natural language time parsing ("remind me in 2 hours", "tomorrow at 9am")
- Snooze functionality for flexible scheduling

**Focus Sessions**
- Start focused work sessions and track duration
- View statistics on total focus time
- Earn XP for maintaining focus sessions
- Team focus leaderboards

**Pomodoro Timer**
- Built-in Pomodoro technique support (25 min work, 5 min break)
- Customizable work/break intervals
- Track completed Pomodoro sessions
- Automatic reminders for breaks

**Do Not Disturb Mode**
- Activate DND to minimize interruptions
- Automatic Discord status changes
- Temporary mute notifications
- Set DND duration or end manually

**Countdown Timers**
- Create countdown timers for deadlines, releases, or events
- Public countdowns visible to the whole team
- Automatic notifications when time is up

### 📅 Meetings & Events

**Meeting Scheduler**
- Schedule team meetings with date, time, and duration
- Add meeting agendas before the meeting
- Take and save meeting notes
- Automatic reminders before meetings start

**RSVP System**
- Track attendance with Yes/No/Maybe responses
- See who's attending at a glance
- Send reminders to people who haven't responded
- Export attendee lists

**Event Management**
- Schedule team events, deadlines, and important dates
- Set event reminders for all participants
- Attach descriptions, locations, and links to events

**Recurring Events**
- Create recurring meetings (daily standups, weekly syncs, sprint planning)
- Flexible recurrence patterns (every X days, weekly on specific days, monthly)
- Manage recurring event series

### 🎮 Gamification & Engagement

**XP & Leveling System**
- Earn experience points for completing tasks, coding, and participating
- Level up and unlock new badges and privileges
- Custom XP multipliers for different activities
- Team XP leaderboards

**Achievement Badges**
- Unlock unique badges for reaching milestones:
  - "First Commit" - Complete your first task
  - "Code Warrior" - 100+ hours of coding
  - "Task Master" - Complete 50 tasks
  - "Early Bird" - Complete tasks before their deadline 10 times
  - And many more!

**Coding Challenges**
- Create and participate in coding challenges
- Set challenge parameters (difficulty, duration, language)
- Award XP and special badges for challenge completion
- Community-driven challenge creation

**Streak Tracking**
- Track consecutive days of coding or task completion
- Maintain your streak to earn bonus XP
- Streak milestones unlock special badges
- Compete with teammates for longest streaks

### 🔔 Notifications & Alerts

- Task deadline reminders
- Meeting notifications
- Blocker alerts
- New task assignments
- Milestone completion celebrations
- Custom notification preferences per user

### 📊 Reports & Analytics

- Weekly team productivity reports
- Individual performance summaries
- Task completion rates and trends
- Coding time analytics
- Project health dashboards

---
## 📚 Usage

### Basic Commands

Here are some essential commands to get started. All commands use the `/` slash command format:

#### Task Management

```
/task create [title] [description] [priority] [deadline]
  Create a new team task

/task assign [task_id] [@user]
  Assign a task to a team member

/task complete [task_id]
  Mark a task as completed

/task list
  View all active team tasks

/task my
  View your assigned tasks

/personal add [task]
  Add a personal task to your to-do list

/personal list
  View your personal tasks
```

#### Time Management

```
/remind [time] [message]
  Set a reminder (e.g., /remind 30m Review PR)

/focus start
  Start a focus session

/focus stop
  End your current focus session

/pomodoro start
  Start a Pomodoro timer

/dnd [duration]
  Activate Do Not Disturb mode
```

#### Meetings & Events

```
/meeting create [title] [date] [time] [duration]
  Schedule a new meeting

/meeting agenda [meeting_id] [agenda_text]
  Add an agenda to a meeting

/meeting rsvp [meeting_id] [yes/no/maybe]
  Respond to a meeting invitation

/meeting notes [meeting_id] [notes]
  Add notes after a meeting
```

#### Code Editor Integration

```
/code stats
  View your coding statistics

/code languages
  See breakdown by programming language

/code leaderboard
  Team coding time leaderboard

/code setup [editor]
  Get setup instructions for your editor
```

#### Gamification

```
/xp
  Check your current XP and level

/badges
  View your unlocked badges

/leaderboard
  See the team XP leaderboard

/challenge create [title] [description] [reward_xp]
  Create a coding challenge
```

### Advanced Features

#### Task Dependencies

```
/task depends [task_id] [depends_on_task_id]
  Set a task dependency

/task dependencies [task_id]
  View all dependencies for a task
```

#### Blockers

```
/blocker report [title] [description] [severity]
  Report a project blocker

/blocker assign [blocker_id] [@user]
  Assign someone to resolve a blocker

/blocker resolve [blocker_id]
  Mark a blocker as resolved
```

#### Recurring Events

```
/event recurring [title] [start_date] [recurrence_pattern]
  Create a recurring event
  Patterns: daily, weekly, monthly
```

---

## 🏗️ Project Structure

```
Kronos_V1/
│
├── bot.py                  # Main bot entry point
├── config.py              # Configuration settings
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables (not in repo)
│
├── cogs/                  # Command modules (cogs)
│   ├── tasks.py          # Task management commands
│   ├── kanban.py         # Kanban board commands
│   ├── time_mgmt.py      # Time management commands
│   ├── meetings.py       # Meeting and event commands
│   ├── code_tracking.py  # Code editor integration
│   └── gamification.py   # XP, levels, and badges
│
├── utils/                 # Utility functions
│   ├── database.py       # Database operations
│   ├── embeds.py         # Embed templates
│   ├── parsers.py        # Input parsing helpers
│   └── validators.py     # Input validation
│
├── models/                # Data models
│   ├── task.py
│   ├── user.py
│   ├── meeting.py
│   └── badge.py
│
├── web/                   # Flask web interface (optional)
│   ├── app.py
│   └── templates/
│
└── tests/                 # Unit tests
    └── test_*.py
```

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **Discord.py** - The excellent Discord API wrapper for Python
- **Flask** - Lightweight web framework for the web interface
- **Contributors** - Thanks to everyone who has contributed to this project

---

## 📮 Contact & Support

- **GitHub Issues**: [Report bugs or request features](https://github.com/dhanunjaya007/Kronos_V1/issues)
- **Developer**: [@dhanunjaya007](https://github.com/dhanunjaya007)
- **Project Link**: [https://github.com/dhanunjaya007/Kronos_V1](https://github.com/dhanunjaya007/Kronos_V1)

---

**⭐ Star this repo if you find it useful! ⭐**

Made with ❤️ by [Dhanunjaya](https://github.com/dhanunjaya007)

</div>
