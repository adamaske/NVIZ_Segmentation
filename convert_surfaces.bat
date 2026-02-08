@echo off
setlocal enabledelayedexpansion

:: ============================================================================
:: Convert FastSurfer/FreeSurfer surfaces to OBJ format for NIRSViz
:: ============================================================================

set DOCKER_IMAGE=deepmi/fastsurfer:latest
set OUTPUT_DIR=%~dp0output

if "%~1"=="" (
    echo.
    echo  Convert FreeSurfer surfaces to OBJ
    echo  ===================================
    echo  Usage: convert_surfaces.bat ^<subject_id^>
    echo.
    echo  Converts lh/rh.pial and lh/rh.white to .obj format.
    echo  Subject must exist in: %OUTPUT_DIR%\^<subject_id^>
    echo.
    exit /b 1
)

set SUBJECT_ID=%~1
set SURF_DIR=%OUTPUT_DIR%\%SUBJECT_ID%\surf

if not exist "%SURF_DIR%" (
    echo [ERROR] Surface directory not found: %SURF_DIR%
    exit /b 1
)

echo Converting surfaces for %SUBJECT_ID%...

for %%S in (lh.pial rh.pial lh.white rh.white) do (
    if exist "%SURF_DIR%\%%S" (
        echo   Converting %%S...
        docker run --rm ^
            -v "%OUTPUT_DIR%":/output ^
            %DOCKER_IMAGE% ^
            mris_convert /output/%SUBJECT_ID%/surf/%%S /output/%SUBJECT_ID%/surf/%%S.obj
        
        if exist "%SURF_DIR%\%%S.obj" (
            echo   [OK] %%S.obj
        ) else (
            echo   [FAIL] %%S.obj
        )
    ) else (
        echo   [SKIP] %%S not found
    )
)

:: Also try to combine left+right pial into a single mesh
echo.
echo  Merging left + right pial into cortex.obj ...

python "%~dp0merge_obj.py" "%SURF_DIR%\lh.pial.obj" "%SURF_DIR%\rh.pial.obj" "%SURF_DIR%\cortex.obj"
if exist "%SURF_DIR%\cortex.obj" (
    echo   [OK] cortex.obj (merged pial surface)
) else (
    echo   [SKIP] merge failed - load lh/rh separately in NIRSViz
)

echo.
echo Done. OBJ files are in: %SURF_DIR%
endlocal
