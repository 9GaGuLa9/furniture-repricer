#!/bin/bash
# ========================================
# Furniture Repricer Scheduler - Linux/Mac
# ========================================

echo "========================================"
echo "Starting Furniture Repricer Scheduler"
echo "========================================"
echo ""

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Activate virtual environment if exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Run scheduler
echo "Starting scheduler daemon..."
python3 run_scheduler.py

# If scheduler exits
echo ""
echo "Scheduler stopped."
