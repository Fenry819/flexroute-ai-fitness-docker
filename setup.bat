@echo off
title FlexRoute Setup
color 0A

echo.
echo ==========================
echo      FLEXROUTE SETUP
echo ==========================
echo.

cd /d "%~dp0"

echo Checking Docker...
docker info >nul 2>&1

if errorlevel 1 (
    echo.
    echo ERROR: Docker Desktop is not running.
    echo Start Docker Desktop and try again.
    echo.
    pause
    exit /b 1
)

echo.
echo Detecting NVIDIA GPU...
nvidia-smi >nul 2>&1

if %errorlevel%==0 (
    echo NVIDIA GPU detected.
    echo Starting FlexRoute in GPU mode...
    docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
) else (
    echo No NVIDIA GPU detected.
    echo Starting FlexRoute in CPU mode...
    docker compose up -d --build
)

if errorlevel 1 (
    echo.
    echo ERROR: Docker services failed to start.
    echo.
    pause
    exit /b 1
)

echo.
echo Pulling Mistral model...
docker compose exec ollama ollama pull mistral

if errorlevel 1 (
    echo.
    echo ERROR: Failed to pull Mistral.
    pause
    exit /b 1
)

echo.
echo Pulling embedding model...
docker compose exec ollama ollama pull nomic-embed-text

if errorlevel 1 (
    echo.
    echo ERROR: Failed to pull nomic-embed-text.
    pause
    exit /b 1
)

echo.
echo Preparing Qdrant knowledge base...
docker compose exec backend python src/document_loader.py

if errorlevel 1 (
    echo.
    echo WARNING: Qdrant knowledge setup failed.
    echo You can retry later with:
    echo docker compose exec backend python src/document_loader.py
    echo.
)

echo.
echo ==========================
echo   FLEXROUTE SETUP COMPLETE
echo ==========================
echo.
echo Next:
echo 1. Install FlexRoute using the Windows installer.
echo 2. Use start_flexroute.bat for normal startup.
echo.

pause