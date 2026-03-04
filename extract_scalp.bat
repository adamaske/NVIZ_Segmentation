@echo off
setlocal enabledelayedexpansion

REM ============================================================================
REM  extract_scalp.bat — Extract scalp surface from T1.mgz (pure Python)
REM
REM  This script replaces the previous mkheadsurf-based approach.
REM  The FastSurfer Docker image ships a stripped-down FreeSurfer that does NOT
REM  include mkheadsurf. Instead, we use a pure Python pipeline:
REM
REM    1. Load T1.mgz with nibabel
REM    2. Threshold + morphological ops to create a head mask
REM    3. Marching cubes (scikit-image) to extract the isosurface
REM    4. Transform to FreeSurfer surface-RAS coordinates
REM    5. Reorient axes to match the rest of the nviz pipeline
REM    6. Export as Wavefront OBJ
REM
REM  No Docker required for this step — just Python + pip packages.
REM
REM  Required packages:  pip install nibabel scipy scikit-image trimesh numpy
REM ============================================================================

if "%~1"=="" (
    echo.
    echo  Usage: extract_scalp.bat ^<subject_id^> [threshold] [smooth] [decimate]
    echo.
    echo  Arguments:
    echo    subject_id   Subject folder name in output\
    echo    threshold    Intensity threshold for head mask (default: 15^)
    echo    smooth       Morphological closing iterations  (default: 2^)
    echo    decimate     Target face count (default: 50000 -^> ~25k vertices^)
    echo.
    echo  Example:
    echo    extract_scalp.bat sub-116
    echo    extract_scalp.bat sub-116 20 3
    echo    extract_scalp.bat sub-116 15 2 80000
    exit /b 1
)

set SUBJECT_ID=%~1
set THRESHOLD=%~2
set SMOOTH=%~3
set DECIMATE=%~4
set "SCRIPT_DIR=%~dp0"

if "%THRESHOLD%"=="" set THRESHOLD=15
if "%SMOOTH%"=="" set SMOOTH=2
if "%DECIMATE%"=="" set DECIMATE=50000

REM --- Check for T1.mgz (FastSurfer output) ---
set "T1_PATH=%SCRIPT_DIR%output\%SUBJECT_ID%\mri\T1.mgz"
if not exist "%T1_PATH%" (
    echo.
    echo  ERROR: T1.mgz not found at: output\%SUBJECT_ID%\mri\T1.mgz
    echo  Run run_fastsurfer.bat first to generate the T1.mgz.
    exit /b 1
)

REM --- Check Python dependencies ---
echo.
echo  Checking Python dependencies ...
python -c "import nibabel, scipy, skimage, trimesh, numpy, fast_simplification" 2>nul
if !ERRORLEVEL! NEQ 0 (
    echo.
    echo  ERROR: Missing Python packages. Install them with:
    echo    pip install nibabel scipy scikit-image trimesh numpy fast-simplification
    exit /b 1
)

set "OUTPUT_PATH=%SCRIPT_DIR%output\%SUBJECT_ID%\surf\scalp.obj"

echo.
echo  ============================================
echo   Scalp Extraction (pure Python^)
echo  ============================================
echo   Subject:    %SUBJECT_ID%
echo   Input:      output\%SUBJECT_ID%\mri\T1.mgz
echo   Output:     output\%SUBJECT_ID%\surf\scalp.obj
echo   Threshold:  %THRESHOLD%
echo   Smooth:     %SMOOTH%
echo   Decimate:   %DECIMATE% faces
echo  ============================================
echo.

python "%SCRIPT_DIR%scripts\extract_scalp.py" ^
    "%T1_PATH%" ^
    "%OUTPUT_PATH%" ^
    --threshold %THRESHOLD% ^
    --smooth %SMOOTH% ^
    --decimate %DECIMATE%

if !ERRORLEVEL! NEQ 0 (
    echo.
    echo  ERROR: Scalp extraction failed.
    echo  Try adjusting --threshold (lower = more inclusive^).
    exit /b 1
)

echo.
echo  ============================================
echo   Done! Output: output\%SUBJECT_ID%\surf\scalp.obj
echo  ============================================
endlocal