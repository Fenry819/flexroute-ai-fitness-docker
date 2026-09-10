@echo off
title FlexRoute Launcher
color 0A

echo =========================================
echo            STARTING FLEXROUTE
echo =========================================
echo.

cd /d "%~dp0"

echo [1/2] Starting Docker services...
docker compose up -d

if errorlevel 1 (
    echo.
    echo ERROR: Docker services could not be started.
    echo Make sure Docker Desktop is running.
    echo.
    pause
    exit /b 1
)

echo.
echo Waiting for FlexRoute backend...
timeout /t 5 /nobreak >nul

echo [2/2] Launching FlexRoute...

start "" "%LOCALAPPDATA%\Programs\FlexRoute\FlexRoute.exe"

echo.
echo FlexRoute started.
timeout /t 2 /nobreak >nul
exit