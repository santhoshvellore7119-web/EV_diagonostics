%% Root Quick Launch for MATLAB ML Model Demonstrator
% In MATLAB Command Window, simply run:
% >> run_matlab_ml_demo

clear; clc; close all;
project_root = fileparts(mfilename('fullpath'));
addpath(genpath(project_root));

fprintf('Starting MATLAB ML Multi-Modal Fusion Model Demonstrator...\n');
demonstrate_ml_fusion_model('all');
