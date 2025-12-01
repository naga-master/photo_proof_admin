#!/bin/bash

# PhotoProof Admin Dashboard Startup Script (Flask with uv)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting PhotoProof Admin Dashboard${NC}"
echo "========================================"

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo -e "${YELLOW}uv not found. Installing uv...${NC}"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# Create virtual environment with uv if it doesn't exist
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}Creating virtual environment with uv...${NC}"
    uv venv
fi

# Install dependencies with uv
echo -e "${YELLOW}Installing dependencies...${NC}"
uv pip install -r requirements.txt

# Start the app
echo ""
echo -e "${GREEN}Starting Flask server on port 8501...${NC}"
echo -e "Signup Page:     ${GREEN}http://localhost:8501/signup${NC}"
echo -e "Admin Dashboard: ${GREEN}http://localhost:8501/admin${NC}"
echo ""
echo -e "${YELLOW}Default credentials: admin / admin123${NC}"
echo ""

uv run python app.py
