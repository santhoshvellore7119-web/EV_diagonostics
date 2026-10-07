@echo off
echo ========================================================================
echo  [MATLAB / SIMULINK LAUNCHER] Starting EV Battery Digital Twin...
echo ========================================================================
cd /d "%~dp0"
"C:\Program Files\MATLAB\R2025b\bin\matlab.exe" -nosplash -r "run('run_matlab.m');"
