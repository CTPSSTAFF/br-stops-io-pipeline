@echo off
TITLE TAZ Data Processor

:: ===================================================================
::  1. Prepare the conda environment (with a fast path)
:: ===================================================================
set PACKAGES_TO_INSTALL=python=3.9 pandas numpy
set PREPARE_ENV=1

ECHO Checking for Conda environment 'brstops_env'...
:: Check if the environment exists
conda env list | findstr /B "brstops_env " > NUL

if %errorlevel% equ 0 (
    ECHO Environment found. Checking for required packages...
    :: If env exists, check if a key package is already installed
    conda list -n brstops_env | findstr /B "pandas " > NUL
    if %errorlevel% equ 0 (
        ECHO Packages found. Skipping installation step.
        set PREPARE_ENV=0
    )
)

:: Only run the slow install/create process if the flag is still 1
if %PREPARE_ENV% equ 1 (
    conda env list | findstr /B "brstops_env " > NUL
    if %errorlevel% equ 0 (
        ECHO Key packages missing. Ensuring all packages are installed...
        ECHO This may take a moment.
        conda install --name brstops_env %PACKAGES_TO_INSTALL% -y
    ) else (
        ECHO Environment not found. Creating it now...
        ECHO This may take several minutes.
        conda create --name brstops_env %PACKAGES_TO_INSTALL% -y
    )

    :: Check if the install or create command failed.
    if %errorlevel% neq 0 (
        ECHO ####################################################################
        ECHO ## FATAL ERROR: Failed to prepare the conda environment.
        ECHO ####################################################################
        GOTO :end
    )
)
ECHO Environment is ready.
ECHO.

:: ===================================================================
::  2. Activate the conda environment.
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

:: ===================================================================
::  3. Get user input and run the Python script.
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