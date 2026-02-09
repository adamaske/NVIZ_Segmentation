@echo off
REM ============================================================================
REM  run_fastsurfer.bat — Run FastSurfer segmentation + surface reconstruction
REM
REM  Usage:  run_fastsurfer.bat <filename.nii.gz> <subject_id>
REM  Example: run_fastsurfer.bat sub-116_ses-BL_T1w.nii.gz sub-116
REM ============================================================================

setlocal

REM --- Validate arguments ---
if "%~1"=="" (
    echo.
    echo  Usage: run_fastsurfer.bat ^<filename.nii.gz^> ^<subject_id^>
    echo  Example: run_fastsurfer.bat sub-116_ses-BL_T1w.nii.gz sub-116
    echo.
    echo  Place your T1w file in the input/ folder first.
    exit /b 1
)

if "%~2"=="" (
    echo.
    echo  ERROR: Please provide a subject ID as the second argument.
    echo  Usage: run_fastsurfer.bat ^<filename.nii.gz^> ^<subject_id^>
    exit /b 1
)

set FILENAME=%~1
set SUBJECT_ID=%~2
set "SCRIPT_DIR=%~dp0"

REM --- Check input file exists ---
if not exist "%SCRIPT_DIR%input\%FILENAME%" (
    echo  ERROR: File not found: input\%FILENAME%
    echo  Place your T1w NIfTI file in the input\ folder.
    exit /b 1
)

REM --- Check license exists ---
if not exist "%SCRIPT_DIR%license\license.txt" (
    echo  ERROR: FreeSurfer license not found at license\license.txt
    echo  Register for free at: https://surfer.nmr.mgh.harvard.edu/registration.html
    echo  Then place the license.txt file in the license\ folder.
    exit /b 1
)

REM --- Check if output already exists ---
if exist "%SCRIPT_DIR%output\%SUBJECT_ID%" (
    echo  WARNING: Output directory output\%SUBJECT_ID%\ already exists.
    echo  FastSurfer may fail or overwrite existing results.
    set /p CONTINUE="  Continue anyway? (y/n): "
    if /i not "%CONTINUE%"=="y" exit /b 0
)

echo.
echo  ============================================
echo   FastSurfer — Brain Segmentation Pipeline
echo  ============================================
echo   Input:   %FILENAME%
echo   Subject: %SUBJECT_ID%
echo   GPU:     Enabled
echo  ============================================
echo.
echo  Starting FastSurfer (this takes ~45-75 minutes)...
echo.

docker run --gpus all ^
    -v "%SCRIPT_DIR%input":/data ^
    -v "%SCRIPT_DIR%output":/output ^
    -v "%SCRIPT_DIR%license":/fs_license ^
    --rm ^
    --user root ^
    deepmi/fastsurfer:latest ^
    --fs_license /fs_license/license.txt ^
    --t1 /data/%FILENAME% ^
    --sid %SUBJECT_ID% ^
    --sd /output ^
    --3T ^
    --threads max ^
    --allow_root

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo  ERROR: FastSurfer exited with error code %ERRORLEVEL%
    echo  Check the output above for details.
    exit /b %ERRORLEVEL%
)

echo.
echo  ============================================
echo   FastSurfer completed successfully!
echo  ============================================
echo   Results in: output\%SUBJECT_ID%\
echo.
echo   Next step: run convert_surfaces.bat %SUBJECT_ID%
echo   to generate OBJ files for NIRSViz.
echo  ============================================

endlocal