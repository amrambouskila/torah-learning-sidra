@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
if "%SIDRA_POSTGRES_PORT%"=="" set SIDRA_POSTGRES_PORT=5524
if "%SIDRA_API_PORT%"=="" set SIDRA_API_PORT=8285
if "%SIDRA_FRONTEND_PORT%"=="" set SIDRA_FRONTEND_PORT=5285
set IMAGE_PREFIX=torah_learning_sidra

:start
docker compose up --build -d
if errorlevel 1 goto failed
call :autoseed
echo.
echo   Torah Learning Sidra
echo   ====================
echo   Sidra         http://localhost:%SIDRA_FRONTEND_PORT%
echo   API           http://localhost:%SIDRA_API_PORT%
echo   API docs      http://localhost:%SIDRA_API_PORT%/docs
echo   PostgreSQL    localhost:%SIDRA_POSTGRES_PORT%   (db: sidra, sidra_test)
echo.
echo   Services are running.
echo.

:menu
echo   [r] restart                        [k] stop, keep images
echo   [q] stop, remove project images    [v] full cleanup (volumes too)
echo.
set "choice="
set /p choice="  > "
if /i "%choice%"=="r" (
    docker compose down
    goto start
)
if /i "%choice%"=="k" (
    docker compose down
    goto done
)
if /i "%choice%"=="q" (
    docker compose down --remove-orphans
    call :remove_images
    goto done
)
if /i "%choice%"=="v" (
    docker compose down --volumes --remove-orphans
    call :remove_images
    goto done
)
echo   Unrecognised option.
echo.
goto menu

:autoseed
REM Seed the catalog only, and only when it is empty. Never "refresh" - that re-crawls Sefaria
REM and streams roughly 656 MB. The calendar is the same kind of thing (a year is ~800 calls), so
REM the ledger is reported rather than seeded here.
where uv >nul 2>&1
if errorlevel 1 exit /b 0
pushd backend
REM The schema has to exist before anything can ask the database a question. "init" is idempotent.
uv run sidra-db init >nul
if errorlevel 1 (
    echo   Could not create the schema; run "uv run sidra-db init" by hand.
    popd
    exit /b 0
)
set "STATUS="
for /f "delims=" %%s in ('uv run sidra-db status 2^>nul') do set "STATUS=%%s"
echo !STATUS! | findstr /c:"catalog empty" >nul
if not errorlevel 1 (
    echo   Catalog is empty; seeding from the committed snapshot...
    uv run sidra-db seed
    if errorlevel 1 echo   Seeding failed; run "uv run sidra-db seed" by hand.
)
REM A copied project folder brings its ledger export but not the Docker volume the database lives
REM in, so this is the step that puts the history back on a new machine. Offline.
echo !STATUS! | findstr /c:"ledger empty" >nul
if not errorlevel 1 (
    if exist data\ledger.json (
        echo   Ledger is empty; importing backend/data/ledger.json...
        uv run sidra-db import
        if errorlevel 1 echo   Import failed; run "uv run sidra-db import" by hand.
    ) else (
        echo   Ledger is empty and there is no export to import. To build one ^(needs the network^):
        echo     cd backend ^&^& uv run sidra-db calendar --start 2026-08-24 ^&^& uv run sidra-db seed-tracks
        echo   Then "uv run sidra-db export" before copying this folder anywhere.
    )
)
popd
exit /b 0

:remove_images
for /f "tokens=*" %%i in ('docker images --format "{{.Repository}}:{{.Tag}}" ^| findstr /b "%IMAGE_PREFIX%"') do docker rmi %%i
exit /b 0

:failed
echo.
echo   docker compose failed. Is Docker Desktop running?
echo.
pause
exit /b 1

:done
pause
exit /b 0
