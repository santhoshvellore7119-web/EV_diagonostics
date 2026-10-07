@echo off
echo ========================================================================
echo  [MATLAB / SIMULINK LAUNCHER] Starting EV Battery Digital Twin...
echo ========================================================================
cd /d "%~dp0"
matlab -nosplash -r "run('launch_simulink.m');"
