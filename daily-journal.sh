#!/bin/bash
#
# Daily Dev Journal Automation
# Extracts today's Cursor conversations and uses cursor-agent to summarize them
# into the dev-journal format.
#

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEV_JOURNAL_DIR="$HOME/workspace/gingerio/dev-journal"
LOG_FILE="$SCRIPT_DIR/journal.log"
PROMPT_TEMPLATE="$SCRIPT_DIR/prompt-template.txt"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

# macOS notification function
notify() {
    local title="$1"
    local message="$2"
    local sound="${3:-default}"  # default, Basso, Blow, Bottle, Frog, Funk, Glass, Hero, Morse, Ping, Pop, Purr, Sosumi, Submarine, Tink
    
    osascript -e "display notification \"$message\" with title \"$title\" sound name \"$sound\"" 2>/dev/null || true
}

# Success notification
notify_success() {
    notify "Dev Journal" "$1" "Glass"
}

# Error notification  
notify_error() {
    notify "Dev Journal Error" "$1" "Basso"
}

# Main function
main() {
    log "Starting daily journal automation"
    
    # Check if dev-journal directory exists
    if [[ ! -d "$DEV_JOURNAL_DIR" ]]; then
        log "ERROR: Dev-journal directory not found at $DEV_JOURNAL_DIR"
        notify_error "Dev-journal directory not found"
        exit 1
    fi
    
    # Check if cursor-agent is available
    if ! command -v cursor-agent &> /dev/null; then
        log "ERROR: cursor-agent not found in PATH"
        notify_error "cursor-agent not found in PATH"
        exit 1
    fi
    
    # Extract today's conversations
    log "Extracting today's conversations..."
    CONVERSATIONS=$("$SCRIPT_DIR/extract_conversations.py" --format json 2>&1) || {
        log "ERROR: Failed to extract conversations"
        notify_error "Failed to extract conversations"
        exit 1
    }
    
    # Check if there are any conversations
    CONV_COUNT=$(echo "$CONVERSATIONS" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
    
    if [[ "$CONV_COUNT" == "0" ]]; then
        log "No conversations found for today. Exiting."
        notify_success "No new conversations to log"
        exit 0
    fi
    
    log "Found $CONV_COUNT conversation(s) to summarize"
    
    # Get today's date for the journal file
    TODAY=$(date '+%Y-%m-%d')
    JOURNAL_FILE="$DEV_JOURNAL_DIR/logs/$TODAY.md"
    
    # Read the prompt template
    if [[ ! -f "$PROMPT_TEMPLATE" ]]; then
        log "ERROR: Prompt template not found at $PROMPT_TEMPLATE"
        notify_error "Prompt template not found"
        exit 1
    fi
    
    PROMPT=$(cat "$PROMPT_TEMPLATE")
    
    # Write conversation data to a file in the dev-journal workspace
    TEMP_DATA_FILE="$DEV_JOURNAL_DIR/.cursor-conversations-temp.json"
    echo "$CONVERSATIONS" > "$TEMP_DATA_FILE"
    
    # Build the prompt with instructions from template
    PROMPT_INSTRUCTIONS=$(cat "$PROMPT_TEMPLATE")
    SHORT_PROMPT="$PROMPT_INSTRUCTIONS

## Data Files

- Conversation data: .cursor-conversations-temp.json
- Today's date: $TODAY  
- Journal file: $JOURNAL_FILE (create with header '# $TODAY' if it doesn't exist)

Read the conversation JSON and process each conversation according to the duplicate handling rules above."
    
    log "Invoking cursor-agent for summarization..."
    
    # Run cursor-agent in print mode to generate the journal entries
    cursor-agent \
        --print \
        --workspace "$DEV_JOURNAL_DIR" \
        --output-format text \
        --approve-mcps \
        --force \
        --model sonnet-4.5 \
        "$SHORT_PROMPT" < /dev/null 2>&1 | tee -a "$LOG_FILE"
    
    AGENT_EXIT_CODE=$?
    
    # Cleanup temp file
    rm -f "$TEMP_DATA_FILE"
    
    AGENT_EXIT_CODE=${PIPESTATUS[0]}
    
    if [[ $AGENT_EXIT_CODE -ne 0 ]]; then
        log "WARNING: cursor-agent exited with code $AGENT_EXIT_CODE"
        notify_error "cursor-agent failed (exit code $AGENT_EXIT_CODE)"
        exit 1
    fi
    
    log "Daily journal automation completed"
    notify_success "Journal updated with $CONV_COUNT conversation(s)"
}

# Run main function
main "$@"
