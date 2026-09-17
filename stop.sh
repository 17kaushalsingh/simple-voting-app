#!/bin/bash

echo "🛑 Stopping application processes..."
if [ -f .app_pids ]; then
    while read pid; do
        # pkill -P kills child processes (useful for npm run dev -> vite)
        pkill -P $pid 2>/dev/null
        kill -9 $pid 2>/dev/null
    done < .app_pids
    rm .app_pids
    echo "✅ Application processes stopped."
else
    echo "⚠️ .app_pids not found. Attempting to force close known processes..."
    pkill -f "python3 app.py"
    pkill -f "dotnet run"
    pkill -f "vite"
fi

echo "🧹 Flushing Redis sessions and queues..."
if command -v redis-cli &> /dev/null; then
    redis-cli flushall
    echo "✅ Redis flushed."
else
    echo "⚠️ redis-cli not found, skipping flush."
fi

echo "🛑 Stopping background infrastructure services..."
brew services stop redis
brew services stop postgresql

echo "✅ All systems offline."
