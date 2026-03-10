#!/usr/bin/env bash
# Start the Domain Expansion backend (which also serves the frontend).
# Installs Python dependencies on first run (or if requirements change).
# Then open http://localhost:5000 in your browser.

set -e
cd "$(dirname "$0")/backend"

echo "Installing dependencies..."
pip install -q -r requirements.txt

echo "Starting server at http://localhost:5000"
python main.py
