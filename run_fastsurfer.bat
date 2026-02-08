@echo off
setlocal enabledelayedexpansion

:: ============================================================================
:: FastSurfer Runner for NIRSViz
:: Runs FastSurfer via Docker Desktop (Windows) with GPU acceleration
:: ============================================================================

:: --- Configuration -----------------------------------------------------------
set DOCKER_IMAGE=deepmi/fastsurfer:latest
set INPUT_DIR=%~dp0input
set OUTPUT_DIR=%~dp0output

:: FreeSurfer license (required even for FastSurfer)
:: Get one free at: https://surfer.nmr.mgh.harvard.edu/registration.html
set LICENSE_FILE=%~dp0license.txt

:: --- Parse arguments ---------------------------------------------------------
if "%~1"=="" (
    echo.
    echo  FastSurfer Runner for NIRSViz
    echo  =============================
    echo.
    echo  Usage:  run_fastsurfer.bat ^<filename.nii.gz^> [subject_id]
    echo.
    echo  Examples:
    echo    run_fastsurfer.bat sub-116_T1w.nii.gz
    echo    run_fastsurfer.bat sub-116_T1w.nii.gz sub-116
    echo.
    echo  Place your T1w NIfTI file in: %INPUT_DIR%
    echo  Results will appear in:       %OUTPUT_DIR%\^<subject_id^>
    echo.
    echo  Prerequisites:
    echo    1. Docker Desktop running with WSL2 backend
    echo    2. NVIDIA Container Toolkit installed
    echo    3. FreeSurfer license.txt in this folder
    echo       ^(Get free at https://surfer.nmr.mgh.harvard.edu/registration.html^)
    echo.
    exit /b 1
)

set INPUT_FILE=%~1

:: Subject ID defaults to filename without extension
if "%~2"=="" (
    set SUBJECT_ID=%~n1
    :: Strip .nii if double extension (.nii.gz)
    set SUBJECT_ID=!SUBJECT_ID:.nii=!
) else (
    set SUBJECT_ID=%~2
)

:: --- Validate ----------------------------------------------------------------
if not exist "%LICENSE_FILE%" (
    echo [ERROR] FreeSurfer license.txt not found at: %LICENSE_FILE%
    echo         Get a free license at: https://surfer.nmr.mgh.harvard.edu/registration.html
    echo         Place the file in this folder as "license.txt"
    exit /b 1
)

if not exist "%INPUT_DIR%\%INPUT_FILE%" (
    echo [ERROR] Input file not found: %INPUT_DIR%\%INPUT_FILE%
    echo         Place your T1w NIfTI file in the input/ folder.
    exit /b 1
)

:: Check Docker is running
docker info >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not running. Start Docker Desktop first.
    exit /b 1
)

:: Check GPU access
docker run --rm --gpus all nvidia/cuda:12.0.0-base-ubuntu22.04 nvidia-smi >nul 2>&1
if errorlevel 1 (
    echo [WARNING] GPU not available via Docker. Will run on CPU (slower).
    echo           Make sure NVIDIA Container Toolkit is installed.
    set GPU_FLAG=
) else (
    echo [OK] GPU detected.
    set GPU_FLAG=--gpus all
)

:: --- Pull image if needed ----------------------------------------------------
echo.
echo [1/3] Pulling FastSurfer Docker image (skip if cached)...
docker pull %DOCKER_IMAGE%

:: --- Run FastSurfer -----------------------------------------------------------
echo.
echo [2/3] Running FastSurfer...
echo       Subject:  %SUBJECT_ID%
echo       Input:    %INPUT_FILE%
echo       Output:   %OUTPUT_DIR%\%SUBJECT_ID%
echo.
echo  This will take approximately:
echo    - Segmentation:        ~1 min  (GPU) / ~15 min (CPU)
echo    - Surface reconstruction: ~45-60 min
echo.

docker run --rm %GPU_FLAG% ^
    -v "%INPUT_DIR%":/input ^
    -v "%OUTPUT_DIR%":/output ^
    -v "%LICENSE_FILE%":/fs_license/license.txt ^
    %DOCKER_IMAGE% ^
    --t1 /input/%INPUT_FILE% ^
    --sid %SUBJECT_ID% ^
    --sd /output ^
    --fs_license /fs_license/license.txt ^
    --parallel --threads 4

if errorlevel 1 (
    echo.
    echo [ERROR] FastSurfer failed. Check the output above for details.
    exit /b 1
)

:: --- Convert surfaces to OBJ --------------------------------------------------
echo.
echo [3/3] Converting surfaces to OBJ for NIRSViz...

set SURF_DIR=%OUTPUT_DIR%\%SUBJECT_ID%\surf

:: Use FreeSurfer's mris_convert inside the same Docker container
for %%S in (lh.pial rh.pial lh.white rh.white) do (
    docker run --rm ^
        -v "%OUTPUT_DIR%":/output ^
        %DOCKER_IMAGE% ^
        mris_convert /output/%SUBJECT_ID%/surf/%%S /output/%SUBJECT_ID%/surf/%%S.obj
    
    if exist "%SURF_DIR%\%%S.obj" (
        echo   [OK] %%S.obj
    ) else (
        echo   [WARN] Failed to convert %%S
    )
)

:: --- Done --------------------------------------------------------------------
echo.
echo ============================================================================
echo  DONE! Results in: %OUTPUT_DIR%\%SUBJECT_ID%
echo ============================================================================
echo.
echo  Files for NIRSViz:
echo    Pial surfaces (cortex):
echo      %SURF_DIR%\lh.pial.obj
echo      %SURF_DIR%\rh.pial.obj
echo.
echo    White matter surfaces:
echo      %SURF_DIR%\lh.white.obj
echo      %SURF_DIR%\rh.white.obj
echo.
echo    Segmentation volume:
echo      %OUTPUT_DIR%\%SUBJECT_ID%\mri\aseg.mgz
echo.
echo  Load these in NIRSViz via: Anatomy ^> Import FreeSurfer Subject
echo ============================================================================

endlocal
