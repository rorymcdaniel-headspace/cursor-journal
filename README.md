# Cursor Journal

Automatically summarize your daily Cursor AI conversations and add them to your dev-journal.

## Overview

This tool extracts conversations from Cursor's local SQLite database, uses `cursor-agent` to generate formatted summaries, and appends them to your dev-journal. It can run manually or be scheduled to run automatically at end-of-day.

## Features

- Extracts all Cursor AI conversations from the current day
- Uses cursor-agent to intelligently summarize and categorize entries
- Formats entries in a consistent dev-journal structure
- Automatically commits and pushes to your dev-journal repo
- Supports scheduled execution via macOS launchd

## Prerequisites

- macOS (uses launchd for scheduling)
- [Cursor](https://cursor.sh/) IDE installed
- `cursor-agent` CLI installed and authenticated (`cursor-agent login`)
- Python 3.8+
- Git

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/rorymcdaniel-headspace/cursor-journal.git ~/.local/bin/cursor-journal
```

### 2. Make scripts executable

```bash
chmod +x ~/.local/bin/cursor-journal/extract_conversations.py
chmod +x ~/.local/bin/cursor-journal/daily-journal.sh
```

### 3. Configure your dev-journal path

Edit `daily-journal.sh` and update the `DEV_JOURNAL_DIR` variable to point to your dev-journal repository:

```bash
DEV_JOURNAL_DIR="$HOME/workspace/your-org/dev-journal"
```

### 4. Install the launchd scheduler (optional)

Copy the plist to your LaunchAgents directory:

```bash
cp ~/.local/bin/cursor-journal/com.user.cursor-journal.plist ~/Library/LaunchAgents/
```

Edit the plist to update paths for your username:

```bash
# Update the path in ProgramArguments and HOME environment variable
nano ~/Library/LaunchAgents/com.user.cursor-journal.plist
```

Load the scheduler:

```bash
launchctl load ~/Library/LaunchAgents/com.user.cursor-journal.plist
```

The job will run daily at 6 PM. To change the time, edit the `StartCalendarInterval` in the plist.

## Usage

### Manual execution

Run the full pipeline manually:

```bash
~/.local/bin/cursor-journal/daily-journal.sh
```

### View today's conversations

Extract and display conversations without journaling:

```bash
~/.local/bin/cursor-journal/extract_conversations.py --format summary
```

### Extract as JSON

Get raw conversation data:

```bash
~/.local/bin/cursor-journal/extract_conversations.py --format json
```

### Extract for a specific date

```bash
~/.local/bin/cursor-journal/extract_conversations.py --date 2026-01-28 --format summary
```

## Journal Entry Format

Entries are formatted as:

```markdown
## [HH:MM] Brief Summary

**Type:** feature | bugfix | refactor | infra | learning | planning
**Impact:** low | medium | high
**Context:** [project/topic]

Description of what was accomplished.

**AI Assistance:** How AI helped
```

## How It Works

1. **Extraction**: `extract_conversations.py` queries Cursor's SQLite database at:
   ```
   ~/Library/Application Support/Cursor/User/globalStorage/state.vscdb
   ```

2. **Filtering**: Only conversations created or updated today are included

3. **Summarization**: `cursor-agent` reads the conversation data and generates formatted journal entries using the `sonnet-4.5` model

4. **Output**: Entries are appended to your daily journal file and committed to git

## Configuration

### Changing the model

Edit `daily-journal.sh` to use a different model:

```bash
--model gpt-5.2  # or any model from: cursor-agent --list-models
```

### Changing the schedule

Edit the plist's `StartCalendarInterval`:

```xml
<key>StartCalendarInterval</key>
<dict>
    <key>Hour</key>
    <integer>18</integer>  <!-- 6 PM -->
    <key>Minute</key>
    <integer>0</integer>
</dict>
```

Then reload:

```bash
launchctl unload ~/Library/LaunchAgents/com.user.cursor-journal.plist
launchctl load ~/Library/LaunchAgents/com.user.cursor-journal.plist
```

## Logs

- Main log: `~/.local/bin/cursor-journal/journal.log`
- stdout: `/tmp/cursor-journal.stdout.log`
- stderr: `/tmp/cursor-journal.stderr.log`

## Troubleshooting

### cursor-agent hangs

Ensure stdin is redirected from `/dev/null` when running headless:

```bash
cursor-agent --print "prompt" < /dev/null
```

### "resource_exhausted" error

This usually indicates rate limiting. Try:
- Waiting a few minutes
- Using a different model (e.g., `sonnet-4.5` instead of `gemini-3-flash`)

### Scheduler not running

Check if it's loaded:

```bash
launchctl list | grep cursor-journal
```

Check logs for errors:

```bash
cat /tmp/cursor-journal.stderr.log
```

## Uninstalling

```bash
# Unload the scheduler
launchctl unload ~/Library/LaunchAgents/com.user.cursor-journal.plist

# Remove files
rm ~/Library/LaunchAgents/com.user.cursor-journal.plist
rm -rf ~/.local/bin/cursor-journal
```

## License

MIT
