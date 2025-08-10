@echo off
:: AI Automation Factory - Start Script
:: This script sets up and starts the AI Automation Factory

setlocal enabledelayedexpansion

:: Configuration
set PYTHON=python
set VENV_NAME=venv
set LOG_FILE=logs\startup_%date:~-4,4%%date:~-10,2%%date:~-7,2%_%time:~0,2%%time:~3,2%.log

:: Create logs directory if it doesn't exist
if not exist "logs" mkdir logs

:: Log function
:log
    echo [%date% %time%] %* >> "%LOG_FILE%"
    echo [%time%] %*
    goto :eof

:: Start logging
call :log "Starting AI Automation Factory setup..."

:: Check if running as administrator
net session >nul 2>&1
if %errorLevel% == 0 (
    call :log "Running with administrator privileges"
    set IS_ADMIN=1
) else (
    call :log "Running without administrator privileges (some features may be limited)"
    set IS_ADMIN=0
)

:: Check Python installation
call :log "Checking Python installation..."
python --version >nul 2>&1
if %errorLevel% neq 0 (
    call :log "Python not found. Please install Python 3.9 or later and add it to PATH."
    call :log "Download Python from: https://www.python.org/downloads/"
    pause
    exit /b 1
)

:: Create and activate virtual environment
if not exist "%VENV_NAME%" (
    call :log "Creating virtual environment..."
    %PYTHON% -m venv %VENV_NAME%
    if %errorLevel% neq 0 (
        call :log "Failed to create virtual environment"
        pause
        exit /b 1
    )
)

call :log "Activating virtual environment..."
call %VENV_NAME%\Scripts\activate.bat
if %errorLevel% neq 0 (
    call :log "Failed to activate virtual environment"
    pause
    exit /b 1
)

:: Install dependencies
call :log "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
if %errorLevel% neq 0 (
    call :log "Failed to install dependencies"
    pause
    exit /b 1
)

:: Check if service is installed
sc query "AIFactoryDriveSync" >nul 2>&1
if %errorLevel% == 0 (
    call :log "AI Factory service is installed"
    set SERVICE_INSTALLED=1
) else (
    call :log "AI Factory service is not installed"
    set SERVICE_INSTALLED=0
)

:: Ask user for action
:menu
    echo.
    echo ========================================
    echo    AI Automation Factory - Main Menu    
    echo ========================================
    echo.
    echo 1. Start in console mode
    echo 2. Install/Update Windows Service
    echo 3. Start Windows Service
    echo 4. Stop Windows Service
    echo 5. Open web interface
    echo 6. Exit
    echo.
    set /p CHOICE="Enter your choice (1-6): "

    if "%CHOICE%"=="1" goto console_mode
    if "%CHOICE%"=="2" goto install_service
    if "%CHOICE%"=="3" goto start_service
    if "%CHOICE%"=="4" goto stop_service
    if "%CHOICE%"=="5" goto web_interface
    if "%CHOICE%"=="6" goto exit_script
    goto menu

:console_mode
    call :log "Starting in console mode..."
    python -m workflows.drive_sync
    pause
    goto menu

:install_service
    if %IS_ADMIN%==0 (
        call :log "Administrator privileges required to install service"
        pause
        goto menu
    )
    call :log "Installing Windows service..."
    python -m workflows.service_manager install
    if %errorLevel% neq 0 (
        call :log "Failed to install service"
    ) else (
        call :log "Service installed successfully"
    )
    pause
    goto menu

:start_service
    if %SERVICE_INSTALLED%==0 (
        call :log "Service is not installed. Please install it first."
        pause
        goto menu
    )
    call :log "Starting Windows service..."
    net start "AIFactoryDriveSync"
    if %errorLevel% neq 0 (
        call :log "Failed to start service"
    ) else (
        call :log "Service started successfully"
    )
    pause
    goto menu

:stop_service
    if %SERVICE_INSTALLED%==0 (
        call :log "Service is not installed."
        pause
        goto menu
    )
    call :log "Stopping Windows service..."
    net stop "AIFactoryDriveSync"
    if %errorLevel% neq 0 (
        call :log "Failed to stop service"
    ) else (
        call :log "Service stopped successfully"
    )
    pause
    goto menu

:web_interface
    call :log "Starting web interface..."
    start "" "http://localhost:8000"
    uvicorn main:app --reload
    goto menu

:exit_script
    call :log "Exiting AI Automation Factory"
    exit /b 0
