#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

# Start Flask backend in the background
if ! [ -x "$(pip -v Flask)" ]; then
    echo "flask not found, installing..."
    # Installation commands go here
    pip install flask
else
    echo "flask is already installed."
fi
cd "$ROOT/backend"
python main.py &
BACKEND_PID=$!

# Kill backend when this script exits (Ctrl+C or any signal)
trap "kill $BACKEND_PID 2>/dev/null" EXIT

# Start Vite frontend in the foreground
if ! [ -x "$(npm -v vite)" ]; then
    echo "vite not found, installing..."
    # Installation commands go here 
    npm install vite
else
    echo "vite is already installed."
fi
cd "$ROOT/frontend"
npm run dev
