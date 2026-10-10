%% Master Advanced Diagnostics Runner
% Runs full-system multi-modal benchmark:
% 1. 2-RC ECM Parameter Estimation via RLS
% 2. Multi-Modal Acoustic Time-of-Flight & Attenuation Dispersion
% 3. Closed-Loop Active Rebalancing Deplating Simulation
% 4. Publication Scorecards and Figure Exports

disp('================================================================');
disp('   EV BATTERY MULTI-MODAL DIAGNOSTIC SYSTEM - ADVANCED BENCHMARK');
disp('================================================================');

% Initialize simulation environment
addpath(fullfile(pwd, 'utils'));
addpath(fullfile(pwd, 'scripts'));
addpath(fullfile(pwd, 'models'));

run_all_scenarios;
disp('[SUCCESS] Advanced multi-modal simulation finished cleanly.');
