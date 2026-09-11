function modelName = buildSimscapeModel(p, modelName)
%BUILDSIMSCAPEMODEL Build the Simscape Electrical model programmatically.
%
%   The model is built by script rather than shipped as a .slx so that it can
%   live in version control as readable text and be rebuilt for any connection
%   point without opening the editor.
%
%   Topology, which is the Malian case rather than a generic one:
%
%     average converter -- Lf,Rf filter -- point of common coupling
%                                       -- Lg,Rg Thevenin network -- source
%
%   The Thevenin impedance is the IEC 60909 fault level at the plant's actual
%   busbar, so the short-circuit ratio in the simulation is the one the plant
%   will see.
%
%   Requires Simscape Electrical (Specialized Power Systems).

    if nargin < 2 || isempty(modelName)
        modelName = ['mali_' matlab.lang.makeValidName(p.name)];
    end

    if bdIsLoaded(modelName)
        close_system(modelName, 0);
    end
    new_system(modelName);
    load_system('powerlib');

    add_block('powerlib/powergui', [modelName '/powergui'], ...
        'Position', [20 20 80 60]);
    set_param([modelName '/powergui'], 'SimulationMode', 'Discrete', ...
        'SampleTime', num2str(p.controlDelay / 3));

    % --- network: a stiff source behind the Thevenin impedance of the busbar
    add_block('powerlib/Electrical Sources/Three-Phase Source', ...
        [modelName '/Grid'], 'Position', [60 200 120 280]);
    set_param([modelName '/Grid'], ...
        'Vn', num2str(p.Vbase), ...
        'Freq', num2str(p.fNom), ...
        'SpecifyImpedance', 'Source', ...
        'SourceType', 'RL', ...
        'R', num2str(p.Rg), ...
        'L', num2str(p.Lg));

    % --- converter filter
    add_block('powerlib/Elements/Three-Phase Series RLC Branch', ...
        [modelName '/Filter'], 'Position', [200 200 260 280]);
    set_param([modelName '/Filter'], 'BranchType', 'RL', ...
        'Resistance', num2str(p.Rf), 'Inductance', num2str(p.Lf));

    % --- averaged converter, driven by the modulation index from the control
    add_block('powerlib/Power Electronics/Average-Model Based VSC', ...
        [modelName '/Converter'], 'Position', [340 200 420 280]);
    set_param([modelName '/Converter'], 'Vdc', num2str(2 * p.Vbase * sqrt(2/3)));

    % --- measurements
    add_block('powerlib/Measurements/Three-Phase V-I Measurement', ...
        [modelName '/PCC'], 'Position', [140 200 180 280]);
    set_param([modelName '/PCC'], 'VoltageMeasurement', 'phase-to-ground', ...
        'CurrentMeasurement', 'yes', 'UseLabels', 'on', ...
        'VoltageLabel', 'Vpcc', 'CurrentLabel', 'Iconv');

    % --- control: the same structure as the Python reference
    mali.addControlSubsystem(modelName, p);

    % --- connections
    add_line(modelName, 'Grid/RConn1', 'PCC/LConn1', 'autorouting', 'on');
    add_line(modelName, 'PCC/RConn1', 'Filter/LConn1', 'autorouting', 'on');
    add_line(modelName, 'Filter/RConn1', 'Converter/LConn1', 'autorouting', 'on');
    add_line(modelName, 'Control/1', 'Converter/1', 'autorouting', 'on');

    set_param(modelName, 'StopTime', '1.0', 'Solver', 'ode23tb', ...
        'RelTol', '1e-6', 'AbsTol', '1e-8');
    save_system(modelName);
end
