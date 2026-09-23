@echo off
title FlexRoute Launcher
color 0A

echo.
echo =========================================
echo            STARTING FLEXROUTE
echo =========================================
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
echo [1/3] Detecting hardware...

nvidia-smi >nul 2>&1

if %errorlevel%==0 (
    echo NVIDIA GPU detected.
    echo Starting GPU mode...
    docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
) else (
    echo No NVIDIA GPU detected.
    echo Starting CPU mode...
    docker compose up -d
)

if errorlevel 1 (
    echo.
    echo ERROR: Docker services could not be started.
    pause
    exit /b 1
)

echo.
echo [2/3] Waiting for backend...
timeout /t 5 /nobreak >nul

echo.
echo [3/3] Looking for FlexRoute...

set "FLEXROUTE_SHORTCUT="

for /f "delims=" %%F in ('dir /b /s "%APPDATA%\Microsoft\Windows\Start Menu\Programs\*FlexRoute*.lnk" 2^>nul') do (
    set "FLEXROUTE_SHORTCUT=%%F"
)

if not defined FLEXROUTE_SHORTCUT (
    for /f "delims=" %%F in ('dir /b /s "%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs\*FlexRoute*.lnk" 2^>nul') do (
        set "FLEXROUTE_SHORTCUT=%%F"
    )
)

if not defined FLEXROUTE_SHORTCUT (
    for /f "delims=" %%F in ('dir /b /s "%USERPROFILE%\Desktop\*FlexRoute*.lnk" 2^>nul') do (
        set "FLEXROUTE_SHORTCUT=%%F"
    )
)

if defined FLEXROUTE_SHORTCUT (
    echo FlexRoute found.
    start "" "%FLEXROUTE_SHORTCUT%"
) else (
    echo.
    echo ERROR: FlexRoute installation shortcut could not be found.
    echo.
    echo Try opening FlexRoute once from the Windows Start Menu.
    echo If it is not listed there, reinstall FlexRoute with
    echo "Create Start Menu Shortcut" enabled.
    echo.
    pause
    exit /b 1
)

echo.
echo FlexRoute started successfully.
timeout /t 2 /nobreak >nul
exit