function results = runStudies(outputDir)
%RUNSTUDIES Run the converter studies and write the same tables as the Python
%reference implementation, so the two can be compared row for row.
%
%   RESULTS = MALI.RUNSTUDIES() writes to results/ next to this package.

    if nargin < 1 || isempty(outputDir)
        here = fileparts(fileparts(mfilename('fullpath')));
        outputDir = fullfile(here, '..', 'results', 'matlab');
    end
    if ~isfolder(outputDir)
        mkdir(outputDir);
    end

    data = mali.caseData();
    points = mali.gridStrength(data);

    fprintf('Connection points\n');
    strength = table();
    for k = 1:numel(points)
        p = points(k);
        fprintf('  %-16s %-16s SCR %5.2f  %s\n', p.plant, p.bus, p.scr, p.strength);
        strength = [strength; struct2table(p, 'AsArray', true)]; %#ok<AGROW>
    end
    writetable(strength, fullfile(outputDir, 'grid_strength.csv'));

    % Step response at each connection point, with the design that suits it.
    rows = table();
    for k = 1:numel(points)
        p = mali.inverterParameters(points(k));
        model = mali.buildSimscapeModel(p);
        simOut = sim(model, 'StopTime', '1.0');
        metrics = mali.extractMetrics(simOut, p);
        rows = [rows; struct2table(metrics, 'AsArray', true)]; %#ok<AGROW>
        close_system(model, 0);
    end
    writetable(rows, fullfile(outputDir, 'step_response.csv'));

    % Validation sweep: the same converter against a weakening network.
    ratios = [8 5 3 2 1.5 1.2 1.0];
    sweep = table();
    template = points(1);
    for scr = ratios
        point = template;
        point.sk_mva = scr * point.plant_mw;
        z = point.vn_kv^2 / point.sk_mva;
        point.grid_r_ohm = z / hypot(1, 6);
        point.grid_l_h = (point.grid_r_ohm * 6) / (2 * pi * 50);
        point.scr = scr;
        p = mali.inverterParameters(point, 'PllBandwidthHz', 20);
        model = mali.buildSimscapeModel(p, 'mali_sweep');
        try
            simOut = sim(model, 'StopTime', '1.0');
            metrics = mali.extractMetrics(simOut, p);
        catch err
            metrics = struct('name', p.name, 'scr', scr, 'stable', false, ...
                             'diverged', true, 'note', err.identifier);
        end
        metrics.target_scr = scr;
        sweep = [sweep; struct2table(metrics, 'AsArray', true)]; %#ok<AGROW>
        close_system(model, 0);
    end
    writetable(sweep, fullfile(outputDir, 'strength_sweep.csv'));

    results = struct('strength', strength, 'step', rows, 'sweep', sweep);
    fprintf('\nTables written to %s\n', outputDir);
    fprintf(['Compare them against the Python reference with\n' ...
             '  mali-simscape --studies compare\n']);
end
