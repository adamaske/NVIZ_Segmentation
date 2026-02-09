@echo off
REM ============================================================================
REM  verify_setup.bat — Check that Docker + GPU + FastSurfer image are working
REM ============================================================================

echo.
echo  Checking Docker...
docker --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo  [FAIL] Docker not found. Install Docker Desktop.
    exit /b 1
)
echo  [OK] Docker found

echo.
echo  Checking NVIDIA GPU access in Docker...
docker run --gpus all --rm nvidia/cuda:12.0.0-base-ubuntu22.04 nvidia-smi >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo  [FAIL] GPU not accessible in Docker.
    echo         Check NVIDIA drivers and Docker GPU settings.
    exit /b 1
)
echo  [OK] GPU accessible

echo.
echo  Checking FastSurfer image...
docker image inspect deepmi/fastsurfer:latest >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo  [MISSING] FastSurfer image not found.
    echo            Run: docker pull deepmi/fastsurfer:latest
    exit /b 1
)
echo  [OK] FastSurfer image present

echo.
echo  Checking FreeSurfer license...
if exist "%~dp0license\license.txt" (
    echo  [OK] license.txt found
) else (
    echo  [MISSING] license\license.txt not found
    echo            Register at: https://surfer.nmr.mgh.harvard.edu/registration.html
)

echo.
echo  ============================================
echo   Setup verification complete!
echo  ============================================
