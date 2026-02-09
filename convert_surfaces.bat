@echo off
setlocal enabledelayedexpansion

REM ============================================================================
REM  convert_surfaces.bat — Convert FreeSurfer surfaces to STL
REM ============================================================================

if "%~1"=="" (
    echo.
    echo  Usage: convert_surfaces.bat ^<subject_id^>
    exit /b 1
)

set SUBJECT_ID=%~1
set SCRIPT_DIR=%~dp0

REM --- Check for FastSurfer output ---
if not exist "%SCRIPT_DIR%output\%SUBJECT_ID%\surf\lh.pial" (
    echo  ERROR: No FastSurfer output found for subject "%SUBJECT_ID%"
    exit /b 1
)

echo.
echo  Converting surfaces to STL for: %SUBJECT_ID%
echo.

REM --- Convert each surface ---
for %%S in (lh.pial rh.pial lh.white rh.white) do (
    set "BASENAME=%%S"
    set "CLEAN_NAME=!BASENAME:.=_!"
    
    echo  Converting %%S --^> !CLEAN_NAME!.stl ...

    docker run --rm ^
        --user 0:0 ^
        -v "%SCRIPT_DIR%output":/output ^
        -v "%FS_LICENSE%":/license.txt ^
        -e FS_LICENSE=/license.txt ^
        --entrypoint mris_convert ^
        deepmi/fastsurfer:latest ^
        /output/%SUBJECT_ID%/surf/%%S ^
        /output/%SUBJECT_ID%/surf/!CLEAN_NAME!.stl
    
    if !ERRORLEVEL! NEQ 0 (
        echo     WARNING: Failed to convert %%S
    )
)

echo.
echo  ============================================
echo   Conversion complete!
echo  ============================================
echo.
echo  Check this folder: output\%SUBJECT_ID%\surf\
endlocal