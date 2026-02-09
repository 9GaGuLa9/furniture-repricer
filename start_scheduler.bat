@echo off
REM ========================================
REM Furniture Repricer Scheduler - Windows
REM ========================================

echo ========================================
echo Starting Furniture Repricer Scheduler
echo ========================================
echo.

REM Activate virtual environment if exists
if exist venv\Scripts\activate.bat (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
)

REM Run scheduler
echo Starting scheduler daemon...
python run_scheduler.py

REM If scheduler exits
echo.
echo Scheduler stopped.
pause
