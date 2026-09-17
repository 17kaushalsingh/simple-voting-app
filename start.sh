#!/bin/bash

echo "🚀 Starting infrastructure services..."
brew services start postgresql
brew services start redis

echo "⏳ Waiting for services to initialize..."
sleep 3

echo "🐍 Starting Voting App (Flask)..."
cd VotingApp
python3 app.py > flask.log 2>&1 &
VOTING_APP_PID=$!
cd ..

echo "⚙️ Starting C# Worker..."
cd VotingWorker
dotnet run > worker.log 2>&1 &
WORKER_PID=$!
cd ..

echo "⚛️ Starting Results App (React)..."
cd ResultsApp
npm run dev > react.log 2>&1 &
RESULTS_APP_PID=$!
cd ..

echo "✅ All services started in the background."
echo "👉 Voting App: http://127.0.0.1:5000"
echo "👉 Results App: http://localhost:5173"

# Save PIDs
echo "$VOTING_APP_PID" > .app_pids
echo "$WORKER_PID" >> .app_pids
echo "$RESULTS_APP_PID" >> .app_pids

echo "📝 Logs are being written to VotingApp/flask.log, VotingWorker/worker.log, and ResultsApp/react.log"
echo "🛑 Run ./stop.sh to shut down everything gracefully."
