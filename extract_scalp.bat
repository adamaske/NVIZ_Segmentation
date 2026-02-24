@echo off
setlocal enabledelayedexpansion

REM ============================================================================
REM  extract_scalp.bat — Extract scalp surface via FreeSurfer mkheadsurf
REM ============================================================================

if "%~1"=="" (
    echo.
    echo  Usage: extract_scalp.bat ^<subject_id^>
    echo.
    echo  Example:
    echo    extract_scalp.bat sub-116
    exit /b 1
)

set SUBJECT_ID=%~1
set "SCRIPT_DIR=%~dp0"
set "LICENSE_FILE=%SCRIPT_DIR%license\license.txt"

REM --- Check for FreeSurfer license ---
if not exist "%LICENSE_FILE%" (
    echo  ERROR: FreeSurfer license not found at: license\license.txt
    echo  Register for free at: https://surfer.nmr.mgh.harvard.edu/registration.html
    exit /b 1
)

REM --- Check for FastSurfer output (T1.mgz required) ---
if not exist "%SCRIPT_DIR%output\%SUBJECT_ID%\mri\T1.mgz" (
    echo  ERROR: No T1.mgz found for subject "%SUBJECT_ID%"
    echo  Expected: output\%SUBJECT_ID%\mri\T1.mgz
    echo  Run run_fastsurfer.bat %SUBJECT_ID% first.
    exit /b 1
)

echo.
echo  Extracting scalp surface for: %SUBJECT_ID%
echo.

REM --- Step 1: Run mkheadsurf to generate lh.seghead ---
echo  [1/3] Running mkheadsurf ...

docker run --rm ^
    --user 0:0 ^
    -v "%SCRIPT_DIR%output":/output ^
    -v "%LICENSE_FILE%":/license.txt ^
    -e FS_LICENSE=/license.txt ^
    -e SUBJECTS_DIR=/output ^
    --entrypoint mkheadsurf ^
    deepmi/fastsurfer:latest ^
    -s %SUBJECT_ID%

if !ERRORLEVEL! NEQ 0 (
    echo.
    echo  ERROR: mkheadsurf failed.
    exit /b 1
)

REM --- Check mkheadsurf produced lh.seghead ---
if not exist "%SCRIPT_DIR%output\%SUBJECT_ID%\surf\lh.seghead" (
    echo.
    echo  ERROR: mkheadsurf did not produce lh.seghead
    echo  Expected: output\%SUBJECT_ID%\surf\lh.seghead
    exit /b 1
)

echo  [OK] lh.seghead created.
echo.

REM --- Step 2: Convert lh.seghead to STL ---
echo  [2/3] Running mris_convert lh.seghead -> lh_seghead.stl ...

docker run --rm ^
    --user 0:0 ^
    -v "%SCRIPT_DIR%output":/output ^
    -v "%LICENSE_FILE%":/license.txt ^
    -e FS_LICENSE=/license.txt ^
    --entrypoint mris_convert ^
    deepmi/fastsurfer:latest ^
    /output/%SUBJECT_ID%/surf/lh.seghead ^
    /output/%SUBJECT_ID%/surf/lh_seghead.stl

if !ERRORLEVEL! NEQ 0 (
    echo.
    echo  ERROR: mris_convert failed.
    exit /b 1
)

echo  [OK] lh_seghead.stl created.
echo.

REM --- Step 3: Convert STL to OBJ ---
echo  [3/3] Converting to scalp.obj ...

python "%SCRIPT_DIR%scripts\extract_scalp.py" ^
    "%SCRIPT_DIR%output\%SUBJECT_ID%\surf\lh_seghead.stl" ^
    "%SCRIPT_DIR%output\%SUBJECT_ID%\surf\scalp.obj"

if !ERRORLEVEL! NEQ 0 (
    echo.
    echo  ERROR: STL to OBJ conversion failed.
    exit /b 1
)

echo.
echo  ============================================
echo   Done! Output: output\%SUBJECT_ID%\surf\scalp.obj
echo  ============================================
endlocal
