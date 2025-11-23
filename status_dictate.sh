#!/bin/bash
# Check if dictation service is running

if pgrep -f "dictate.py" > /dev/null; then
    echo "✅ Dictation is running"
    echo ""
    ps aux | grep "[d]ictate.py"
    echo ""
    echo "Recent logs:"
    tail -5 /tmp/dictate.log
else
    echo "❌ Dictation is not running"
    echo "   Start with: ./start_dictate.sh"
fi
