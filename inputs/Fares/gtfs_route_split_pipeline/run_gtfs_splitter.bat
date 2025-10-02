@echo off
TITLE GTFS Filter and Installer

:: This batch file ensures the 'brstops_env' Conda environment exists
:: and has the necessary packages, then runs the Python script.

:: ===================================================================
::  Define required packages
:: ===================================================================
set PIP_PACKAGES=gtfs-kit

ECHO Checking for Conda environment 'brstops_env'...
ECHO.

:: Check if the Conda environment exists.
conda env list | findstr /R "\<brstops_env\>" >nul
if %errorlevel% neq 0 (
    ECHO Conda environment 'brstops_env' not found. Creating it now...
    ECHO.
    conda create --name brstops_env python=3.12 -y
    if %errorlevel% neq 0 (
        ECHO ####################################################################
        ECHO ## FATAL ERROR: Failed to create conda environment 'brstops_env'.
        ECHO ## Please ensure Anaconda is installed and try again.
        ECHO ####################################################################
        GOTO :end
    )
)

ECHO Activating Conda environment 'brstops_env'...
ECHO.
call conda activate brstops_env
if %errorlevel% neq 0 (
    ECHO ####################################################################
    ECHO ## FATAL ERROR: Failed to activate conda environment 'brstops_env'.
    ECHO ####################################################################
    GOTO :end
)

ECHO Environment activated.
ECHO Ensuring 'gtfs-kit' package is installed...
ECHO.

:: This command runs every time to ensure gtfs-kit is installed.
ECHO --- Installing Pip packages ---
pip install %PIP_PACKAGES%
if %errorlevel% neq 0 (
    ECHO ####################################################################
    ECHO ## FATAL ERROR: Failed to install 'gtfs-kit'.
    ECHO ## Please check your internet connection and try again.
    ECHO ####################################################################
    GOTO :end
)

ECHO Package verification complete.
ECHO.

:: ===================================================================
::  Clear the terminal screen
:: ===================================================================
cls

ECHO All packages are ready.
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

:: Execute the Python script.
python gtfs_splitter.py ".\%input_subfolder%"

ECHO.
ECHO ========================================================
ECHO  Script has finished.
ECHO ========================================================

:end
ECHO.
PAUSE