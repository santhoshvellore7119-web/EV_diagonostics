@echo off
echo ========================================================================
echo  [MATLAB ML DEMONSTRATOR] Starting Multi-Modal ML Fusion Demo...
echo ========================================================================
cd /d "%~dp0"
"C:\Program Files\MATLAB\R2025b\bin\matlab.exe" -nosplash -r "run('run_matlab_ml_demo.m');"
