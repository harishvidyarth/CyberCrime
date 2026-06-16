@echo off
REM ─────────────────────────────────────────────────────────────────────────
REM FundTrail — one-click launcher & stopper  (Windows)
REM
REM   Double-click fundtrail.bat          → start (default)
REM   fundtrail.bat start                 → start the server
REM   fundtrail.bat stop                  → stop  the server
REM ─────────────────────────────────────────────────────────────────────────
setlocal EnableDelayedExpansion

cd /d "%~dp0"
set "REPO_DIR=%~dp0"
set "ENV_FILE=%REPO_DIR%.env"

set "ACTION=%~1"
if "!ACTION!"=="" set "ACTION=start"

if /i "!ACTION!"=="start" goto :do_start
if /i "!ACTION!"=="stop"  goto :do_stop
if /i "!ACTION!"=="reset-password" goto :do_reset_password
if /i "!ACTION!"=="reset" goto :do_reset_password

echo Usage: fundtrail.bat [start^|stop^|reset-password]
echo   start           -- (default) build image and launch the server
echo   stop            -- stop the container (case data is preserved)
echo   reset-password  -- regenerate the admin/officer login (data preserved)
pause
exit /b 1

REM ── STOP ──────────────────────────────────────────────────────────────────
:do_stop
where docker >nul 2>&1
if errorlevel 1 (
    echo Docker is not installed -- nothing to stop.
    pause & exit /b 0
)
docker info >nul 2>&1
if errorlevel 1 (
    echo Docker daemon is not running -- nothing to stop.
    pause & exit /b 0
)
echo Stopping FundTrail...
docker compose down
echo.
echo +----------------------------------------------------------+
echo ^|  FundTrail has stopped.                                  ^|
echo ^|                                                          ^|
echo ^|  Your case data is safe -- run fundtrail.bat to restart. ^|
echo +----------------------------------------------------------+
echo.
pause
exit /b 0

REM ── RESET-PASSWORD ──────────────────────────────────────────────────────────
REM Use this if locked out. Regenerates the admin/officer login only (via
REM scripts/create_user.py inside the running container); case data is untouched.
:do_reset_password
where docker >nul 2>&1
if errorlevel 1 (
    echo Docker is not installed -- start FundTrail first: fundtrail.bat
    pause & exit /b 1
)
docker info >nul 2>&1
if errorlevel 1 (
    echo Docker daemon is not running -- start FundTrail first: fundtrail.bat
    pause & exit /b 1
)
docker compose ps 2>nul | findstr /i "fundtrail" >nul 2>&1
if errorlevel 1 (
    echo FundTrail isn't running -- start it first: fundtrail.bat
    pause & exit /b 1
)
echo Resetting admin ^& officer passwords (your case data is NOT affected)...
docker compose exec -T fundtrail python scripts/create_user.py
echo.
echo The new passwords are shown above and saved here:
echo   docker compose exec fundtrail cat /data/INITIAL_CREDENTIALS.txt
echo You'll be asked to set your own password on first login.
pause
exit /b 0

REM ── START ─────────────────────────────────────────────────────────────────
:do_start

REM Step 1: Ensure winget is available
where winget >nul 2>&1
if not errorlevel 1 goto :winget_ready

echo winget not found -- attempting to install App Installer via PowerShell...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "Add-AppxPackage -RegisterByFamilyName -MainPackage Microsoft.DesktopAppInstaller_8wekyb3d8bbwe" ^
    >nul 2>&1

where winget >nul 2>&1
if not errorlevel 1 goto :winget_ready

echo Method A failed -- downloading winget from GitHub...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$url = 'https://github.com/microsoft/winget-cli/releases/latest/download/Microsoft.DesktopAppInstaller_8wekyb3d8bbwe.msixbundle';" ^
    "$out = [System.IO.Path]::Combine($env:TEMP, 'winget.msixbundle');" ^
    "Invoke-WebRequest -Uri $url -OutFile $out -UseBasicParsing;" ^
    "Add-AppxPackage -Path $out"

where winget >nul 2>&1
if errorlevel 1 (
    echo winget could not be installed. Falling back to direct Docker install...
    goto :install_docker_direct
)

:winget_ready
REM Step 2: Check Docker; install via winget if missing
where docker >nul 2>&1
if not errorlevel 1 goto :docker_installed

echo Docker not found -- installing Docker Desktop via winget...
winget install --id Docker.DockerDesktop -e ^
    --silent --accept-package-agreements --accept-source-agreements
if errorlevel 1 (
    echo winget install failed -- falling back to direct download...
    goto :install_docker_direct
)
goto :docker_post_install

:install_docker_direct
echo Downloading Docker Desktop installer (this may take a few minutes)...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$out = [System.IO.Path]::Combine($env:TEMP, 'DockerInstaller.exe');" ^
    "Write-Host 'Downloading...';" ^
    "Invoke-WebRequest -Uri 'https://desktop.docker.com/win/main/amd64/Docker%%20Desktop%%20Installer.exe'" ^
    "    -OutFile $out -UseBasicParsing;" ^
    "Write-Host 'Installing (silent)...';" ^
    "Start-Process -FilePath $out -ArgumentList 'install','--quiet','--accept-license' -Wait"
if errorlevel 1 (
    echo.
    echo Automatic Docker install failed.
    echo Please download Docker Desktop manually:
    echo   https://docs.docker.com/desktop/install/windows-install/
    echo Then re-run this script.
    pause & exit /b 1
)

:docker_post_install
echo.
echo Docker Desktop installed.
echo IMPORTANT: Restart your computer for Docker to work correctly.
echo After restarting, run fundtrail.bat again to launch FundTrail.
echo.
pause & exit /b 0

:docker_installed
REM Step 3: Ensure Docker daemon is running
docker info >nul 2>&1
if not errorlevel 1 goto :docker_ready

echo Docker is installed but not running -- starting Docker Desktop...
start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe" 2>nul
if errorlevel 1 start "" "%LOCALAPPDATA%\Docker\Docker Desktop.exe" 2>nul

echo Waiting for Docker to start (up to 90 s)...
set /a DTRIES=0
:docker_start_wait
set /a DTRIES+=1
if !DTRIES! gtr 30 (
    echo ERROR: Docker daemon still not reachable after 90 s.
    echo Please start Docker Desktop manually and re-run this script.
    pause & exit /b 1
)
timeout /t 3 /nobreak >nul
docker info >nul 2>&1
if errorlevel 1 goto :docker_start_wait

:docker_ready
echo Docker is running.

REM Step 4: Generate .env with a fresh SECRET_KEY on first clone
set "NEED_ENV=0"
if not exist "%ENV_FILE%" set "NEED_ENV=1"
if "!NEED_ENV!"=="0" (
    findstr /b "SECRET_KEY=" "%ENV_FILE%" >nul 2>&1
    if errorlevel 1 set "NEED_ENV=1"
)
if "!NEED_ENV!"=="1" (
    echo First run -- generating .env ...
    set "SK="
    for /f "delims=" %%K in (
        'python -c "import secrets; print(secrets.token_hex(32))" 2^>nul'
    ) do set "SK=%%K"
    if "!SK!"=="" (
        for /f "delims=" %%K in (
            'docker run --rm python:3.11-slim python3 -c "import secrets; print(secrets.token_hex(32))"'
        ) do set "SK=%%K"
    )
    (
        echo # Auto-generated by fundtrail.bat -- keep this file private, never commit it.
        echo SECRET_KEY=!SK!
        echo SESSION_COOKIE_INSECURE=true
        echo PASSWORD_MAX_AGE_DAYS=90
    ) >> "%ENV_FILE%"
    echo   .env created with a fresh SECRET_KEY.
)

REM Step 5: Build image (first run) or restart existing container
echo Starting FundTrail...
docker compose up --build -d

REM Step 6: Wait until /healthz responds
echo Waiting for the app to be ready...
set /a TRIES=0
:health_wait
set /a TRIES+=1
if !TRIES! gtr 30 goto :health_done
docker compose exec -T fundtrail python3 -c ^
    "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5050/healthz',timeout=3).status==200 else 1)" ^
    >nul 2>&1
if not errorlevel 1 goto :health_done
timeout /t 2 /nobreak >nul
goto :health_wait
:health_done

REM Step 7: Print access URLs
set "LAN_IP="
for /f "tokens=2 delims=:" %%A in (
    'ipconfig ^| findstr /i "IPv4" ^| findstr /v "127.0.0.1"'
) do (
    if "!LAN_IP!"=="" set "LAN_IP=%%A"
)
set "LAN_IP=!LAN_IP: =!"
if "!LAN_IP!"=="" set "LAN_IP=^<your-machine-ip^>"

echo.
echo +----------------------------------------------------------+
echo ^|  FundTrail is running                                    ^|
echo ^|                                                          ^|
echo ^|  Local:   http://127.0.0.1:5050                         ^|
echo ^|  LAN:     http://!LAN_IP!:5050
echo ^|                                                          ^|
echo ^|  Share the LAN address with officers on the same Wi-Fi. ^|
echo +----------------------------------------------------------+
echo.
echo First-time admin credentials (change on first login):
echo   docker compose exec fundtrail cat /data/INITIAL_CREDENTIALS.txt
echo.
echo To stop:  fundtrail.bat stop
echo.
pause
