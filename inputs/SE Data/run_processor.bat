@echo off
TITLE TAZ Data Processor

:: This batch file activates the specified Conda environment,
:: prompts the user for a run mode, and then executes the Python script.

ECHO Activating Anaconda environment 'tdm23_env_1'...
ECHO.
call conda activate tdm23_env_1

:: Check if the environment was activated successfully.
if %errorlevel% neq 0 (
    ECHO ####################################################################
    ECHO ## FATAL ERROR: Failed to activate conda environment 'tdm23_env_1'.
    ECHO ## Please ensure Anaconda is installed and the environment exists.
    ECHO ####################################################################
    ECHO.
    GOTO :end
)

ECHO Environment activated successfully.
ECHO.

:: Prompt the user to enter the run mode.
set /p "run_mode_name=Please enter the run mode to execute (e.g., 2025AugRun): "

:: Check if the user actually entered a value.
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

:: Execute the Python script, passing the user's input as the run_mode flag.
python STOPS_SE_Data_Pipeline.py --run_mode %run_mode_name%

ECHO.
ECHO ========================================================
ECHO  Script has finished.
ECHO ========================================================

:end
ECHO.
PAUSE