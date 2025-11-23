#!/bin/bash
# Stop dictation service

if pgrep -f "dictate.py" > /dev/null; then
    pkill -f dictate.py
    echo "✅ Dictation stopped!"
else
    echo "ℹ️  Dictation is not running"
fi
