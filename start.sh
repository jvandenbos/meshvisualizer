#!/bin/bash

echo "🚀 Starting Meshtastic Visualizer..."
echo ""

# Ensure any previously running dev servers are stopped first
echo "🧹 Ensuring no old servers are running..."

kill_if_running() {
  # Kill backend (uvicorn reloader + worker)
  local PIDS
  PIDS=$(pgrep -f "uvicorn\\s+backend\\.main:app" || true)
  if [ -n "$PIDS" ]; then
    echo "   Killing backend PIDs: $PIDS"
    kill $PIDS 2>/dev/null || true
    sleep 1
    # Force kill if still present
    for p in $PIDS; do
      if kill -0 $p 2>/dev/null; then
        echo "   Force killing backend PID: $p"
        kill -9 $p 2>/dev/null || true
      fi
    done
  fi

  # Also kill anything listening on 8000 (defensive)
  local L8000
  L8000=$(lsof -nP -iTCP:8000 -sTCP:LISTEN -t 2>/dev/null || true)
  if [ -n "$L8000" ]; then
    echo "   Killing listeners on 8000: $L8000"
    kill $L8000 2>/dev/null || true
    sleep 1
    for p in $L8000; do
      if kill -0 $p 2>/dev/null; then
        kill -9 $p 2>/dev/null || true
      fi
    done
  fi

  # Kill frontend vite dev server (5173)
  local L5173
  L5173=$(lsof -nP -iTCP:5173 -sTCP:LISTEN -t 2>/dev/null || true)
  if [ -n "$L5173" ]; then
    echo "   Killing frontend (5173) PIDs: $L5173"
    kill $L5173 2>/dev/null || true
    sleep 1
    for p in $L5173; do
      if kill -0 $p 2>/dev/null; then
        kill -9 $p 2>/dev/null || true
      fi
    done
  fi
}

kill_if_running
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8+ first."
    exit 1
fi

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install Node.js 16+ first."
    exit 1
fi

echo "📦 Installing Python dependencies..."
pip3 install -r requirements.txt

echo ""
echo "📦 Installing frontend dependencies..."
cd frontend
npm install
cd ..

echo ""
echo "🔧 Initializing database..."
python3 -c "
import asyncio
from backend.database import Database

async def init():
    db = Database()
    await db.initialize()
    print('✅ Database initialized')

asyncio.run(init())
"

echo ""
echo "🎯 Starting backend server..."
# Start backend in background
uvicorn backend.main:app --reload --port 8000 &
BACKEND_PID=$!

echo "Backend running with PID: $BACKEND_PID"
echo ""

# Wait for backend to start
sleep 3

echo "🎨 Starting frontend development server..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo "Frontend running with PID: $FRONTEND_PID"
echo ""
echo "✅ Meshtastic Visualizer is running!"
echo ""
echo "📱 Open your browser at: http://localhost:5173"
echo "🔌 Backend API available at: http://localhost:8000"
echo "📡 Make sure your RAK 4631 is connected via USB-C"
echo ""
echo "Press Ctrl+C to stop all services..."

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Stopping services..."
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    echo "👋 Goodbye!"
    exit 0
}

# Set up trap to cleanup on Ctrl+C
trap cleanup INT

# Wait for processes
wait
