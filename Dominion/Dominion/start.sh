#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

# Start Flask backend in the background
if pip show flask &> /dev/null; then
    echo "flask is already installed"
else
    echo "flask not found, installing..."
    pip install flask
fi

# Start Vite frontend in the foreground
if [ -f "./frontend/node_modules/.bin/vite" ]; then
    echo "vite is already installed."
else
    echo "vite not found, installing..."
    npm install vite --prefix ./frontend
fi

cd "$ROOT/backend"
python main.py &
BACKEND_PID=$!

# Kill backend when this script exits (Ctrl+C or any signal)
trap "kill $BACKEND_PID 2>/dev/null" EXIT
cd "$ROOT/frontend"
npm run dev
