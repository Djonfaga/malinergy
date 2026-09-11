% Run every converter study.
%
% Requires MATLAB with Simulink and Simscape Electrical (Specialized Power
% Systems). Before running, produce the canonical case:
%
%   cd simulation/core && mali-energy build
%
% Then, from simulation/simscape/matlab:
%
%   >> scripts.run_all

addpath(fileparts(fileparts(mfilename('fullpath'))));
results = mali.runStudies();
disp(results.strength);
