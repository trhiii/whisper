#!/bin/bash
# Start dictation service in the background

cd "$(dirname "$0")"

# Check if already running
if pgrep -f "dictate.py" > /dev/null; then
    echo "❌ Dictation is already running!"
    echo "   Run ./stop_dictate.sh to stop it first."
    exit 1
fi

# Activate venv and start in background
source .venv/bin/activate
nohup python dictate.py > /tmp/dictate.log 2>&1 &

echo "✅ Dictation started!"
echo "   Hold Right Command (⌘) to dictate"
echo "   Check logs: tail -f /tmp/dictate.log"
echo "   Stop with: ./stop_dictate.sh"
