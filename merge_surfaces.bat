@echo off
setlocal enabledelayedexpansion

REM ============================================================================
REM  merge_surfaces.bat — Merge left+right hemispheres into triangulated OBJ
REM ============================================================================

if "%~1"=="" (
    echo.
    echo  Usage: merge_surfaces.bat ^<subject_id^> [surface_type]
    echo.
    echo  surface_type: pial (default) or white
    echo.
    echo  Examples:
    echo    merge_surfaces.bat sub-116
    echo    merge_surfaces.bat sub-116 pial
    echo    merge_surfaces.bat sub-116 white
    exit /b 1
)

set SUBJECT_ID=%~1
set SURFACE=pial
if not "%~2"=="" set SURFACE=%~2

set "SCRIPT_DIR=%~dp0"
set "SURF_DIR=%SCRIPT_DIR%output\%SUBJECT_ID%\surf"

REM --- Check surfaces exist ---
if not exist "%SURF_DIR%\lh.%SURFACE%" (
    echo  ERROR: Left surface not found: %SURF_DIR%\lh.%SURFACE%
    echo  Run FastSurfer first: run_fastsurfer.bat ^<file^> %SUBJECT_ID%
    exit /b 1
)
if not exist "%SURF_DIR%\rh.%SURFACE%" (
    echo  ERROR: Right surface not found: %SURF_DIR%\rh.%SURFACE%
    exit /b 1
)

set OUTPUT_NAME=%SURFACE%.obj
echo.
echo  Merging lh.%SURFACE% + rh.%SURFACE% --^> %OUTPUT_NAME%
echo.

python "%SCRIPT_DIR%scripts\merge_to_obj.py" "%SURF_DIR%\lh.%SURFACE%" "%SURF_DIR%\rh.%SURFACE%" "%SURF_DIR%\%OUTPUT_NAME%"

if !ERRORLEVEL! NEQ 0 (
    echo.
    echo  ERROR: Merge failed. Make sure Python and nibabel are installed:
    echo    pip install -r requirements.txt
    exit /b 1
)

echo.
echo  ============================================
echo   Done! Output: output\%SUBJECT_ID%\surf\%OUTPUT_NAME%
echo  ============================================
endlocal