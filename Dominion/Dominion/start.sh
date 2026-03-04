#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

# Start Flask backend in the background
cd "$ROOT/backend"
python main.py &
BACKEND_PID=$!

# Kill backend when this script exits (Ctrl+C or any signal)
trap "kill $BACKEND_PID 2>/dev/null" EXIT

# Start Vite frontend in the foreground
cd "$ROOT/frontend"
npm run dev
