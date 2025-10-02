@echo off
TITLE GTFS Filter

:: This batch file checks for a Conda environment, creates it if it doesn't exist,
:: and then activates it to run the Python script.

ECHO Checking for Conda environment 'brstops_env'...
ECHO.

:: Check if the Conda environment exists by attempting to activate it.
:: This check is more reliable than parsing the output of `conda env list`.
conda env list | findstr /R "\<brstops_env\>" >nul
if %errorlevel% neq 0 (
    ECHO Conda environment 'brstops_env' not found. Creating it now...
    ECHO.
    conda create --name brstops_env python=3.9 -y
    if %errorlevel% neq 0 (
        ECHO ####################################################################
        ECHO ## FATAL ERROR: Failed to create conda environment 'brstops_env'.
        ECHO ## Please ensure Anaconda is installed and try again.
        ECHO ####################################################################
        GOTO :end
    )
    ECHO Environment created. Installing required packages...
    ECHO.
    call conda activate brstops_env
    pip install gtfs-kit
    if %errorlevel% neq 0 (
        ECHO ####################################################################
        ECHO ## FATAL ERROR: Failed to install 'gtfs-kit'.
        ECHO ## Please check your internet connection and try again.
        ECHO ####################################################################
        GOTO :end
    )
)

ECHO Activating Conda environment 'brstops_env'...
ECHO.
call conda activate brstops_env

ECHO Environment activated successfully.
ECHO.

:: Prompt the user to enter the subfolder name.
set /p "input_subfolder=Please enter the name of the subfolder (e.g., '2024GTFS_RT'): "

:: Check if the user actually entered a value.
if "%input_subfolder%"=="" (
    ECHO.
    ECHO ERROR: No subfolder name was provided. Aborting script.
    GOTO :end
)

ECHO.
ECHO ========================================================
ECHO  Running script for subfolder: %input_subfolder%
ECHO ========================================================
ECHO.

:: Execute the Python script, passing the user's input as a command-line argument.
python gtfs_splitter.py ".\%input_subfolder%"

ECHO.
ECHO ========================================================
ECHO  Script has finished.
ECHO ========================================================

:end
ECHO.
PAUSE
