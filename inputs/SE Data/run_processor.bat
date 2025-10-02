@echo off
TITLE TAZ Data Processor (Optimized)

:: ===================================================================
::  1. Define required packages
:: ===================================================================
@REM set CONDA_PACKAGES=python=3.12
:: The 'import dbf' module is provided by the 'pysal-dbf' package
set PIP_PACKAGES=dbfread dbf pandas

:: ===================================================================
::  2. Check for and create the conda environment if needed
:: ===================================================================
ECHO Checking for Conda environment 'brstops_env'...
conda env list | findstr /B "brstops_env " > NUL

if %errorlevel% neq 0 (
    ECHO Environment 'brstops_env' not found. Creating it now...
    ECHO This may take several minutes.
    conda create --name brstops_env python=3.12 -y
    @REM conda create --name brstops_env %CONDA_PACKAGES% -c conda-forge -y
    if %errorlevel% neq 0 (
        ECHO ####################################################################
        ECHO ## FATAL ERROR: Failed to create the conda environment.
        ECHO ####################################################################
        GOTO :end
    )
)
ECHO Environment found.
ECHO.

:: ===================================================================
::  3. Activate the environment
:: ===================================================================
ECHO Activating Anaconda environment 'brstops_env'...
call conda activate brstops_env

if %errorlevel% neq 0 (
    ECHO ####################################################################
    ECHO ## FATAL ERROR: Failed to ACTIVATE conda environment 'brstops_env'.
    ECHO ####################################################################
    GOTO :end
)
ECHO Environment activated successfully.
ECHO.

@REM :: ===================================================================
@REM ::  4. Fast-path check to see if we can skip installation
@REM :: ===================================================================
@REM ECHO Checking for required packages locally...
@REM :: Check for one conda package AND one pip package. If both exist, skip.
@REM (pip list | findstr /I /B "dbfread " > NUL) && (pip list | findstr /I /B "dbf " > NUL)

@REM if %errorlevel% equ 0 (
@REM     ECHO All key packages found. Skipping installation.
@REM     GOTO :run_script
@REM ) ELSE (
@REM     ECHO One or more packages are missing. Running full installation...
@REM     ECHO.
@REM )

:: ===================================================================
::  5. Full Installation (only runs if check above fails)
:: ===================================================================
ECHO Ensuring all packages are installed. This is fast if they already exist.
ECHO.

@REM ECHO --- Installing Conda packages from conda-forge ---
@REM conda install %CONDA_PACKAGES% -c conda-forge -y
@REM if %errorlevel% neq 0 (
@REM     ECHO ####################################################################
@REM     ECHO ## FATAL ERROR: Failed to install Conda packages.
@REM     ECHO ####################################################################
@REM     GOTO :end
@REM )
@REM ECHO.

ECHO --- Installing Pip packages ---
pip install %PIP_PACKAGES%
if %errorlevel% neq 0 (
    ECHO ####################################################################
    ECHO ## FATAL ERROR: Failed to install Pip packages.
    ECHO ####################################################################
    GOTO :end
)


:: ===================================================================
::  5a. Clear the terminal screen
:: ===================================================================
cls

ECHO All packages are ready.
ECHO.


:run_script
:: ===================================================================
::  6. Get user input and run the Python script
:: ===================================================================
set /p "run_mode_name=Please enter the run mode to execute (e.g., 2025AugRun): "

if "%run_mode_name%"=="" (
    ECHO.
    ECHO ERROR: No run mode was provided. Aborting script.
    GOTO :end
)

ECHO.
ECHO ========================================================
ECHO  Running script with run mode: %run_mode_name%
ECHO ========================================================
ECHO.

python STOPS_SE_Data_Pipeline.py --run_mode %run_mode_name%

ECHO.
ECHO ========================================================
ECHO  Script has finished.
ECHO ========================================================

:end
ECHO.
PAUSE