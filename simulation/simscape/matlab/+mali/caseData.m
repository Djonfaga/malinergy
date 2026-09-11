function data = caseData(exchangePath)
%CASEDATA Read the canonical study case produced by the core package.
%
%   DATA = MALI.CASEDATA() reads build/mali_case.json from the core package.
%   DATA = MALI.CASEDATA(PATH) reads a specific file.
%
%   The same file drives the pandapower, PowerFactory and Modelica models, so
%   the converter studies here are built on the network those studies solved
%   rather than on a separate set of numbers.

    if nargin < 1 || isempty(exchangePath)
        here = fileparts(fileparts(mfilename('fullpath')));
        exchangePath = fullfile(here, '..', '..', 'core', 'build', 'mali_case.json');
    end
    if ~isfile(exchangePath)
        error('mali:caseData:missing', ...
            ['%s not found. Run "mali-energy build" in simulation/core first.'], exchangePath);
    end

    text = fileread(exchangePath);
    data = jsondecode(text);

    if ~startsWith(data.format, 'mali-energy-exchange/')
        error('mali:caseData:format', '%s is not a Mali energy exchange file', exchangePath);
    end
end
