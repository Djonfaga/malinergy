function points = gridStrength(data, shortCircuitPath)
%GRIDSTRENGTH Short-circuit ratio at every photovoltaic connection point.
%
%   The fault levels come from the IEC 60909 calculation performed by the
%   pandapower branch on the same network. Below a short-circuit ratio of about
%   three, a grid-following converter's phase-locked loop begins to interact
%   with the network impedance: the design that is comfortable at Segou is not
%   necessarily comfortable at Kita.

    if nargin < 2 || isempty(shortCircuitPath)
        here = fileparts(fileparts(mfilename('fullpath')));
        shortCircuitPath = fullfile(here, '..', 'data', 'shortcircuit_dry_peak.csv');
    end

    levels = containers.Map('KeyType', 'char', 'ValueType', 'double');
    if isfile(shortCircuitPath)
        table = readtable(shortCircuitPath);
        for k = 1:height(table)
            levels(char(table.bus{k})) = table.sk_max_mva(k);
        end
    end

    buses = containers.Map('KeyType', 'char', 'ValueType', 'any');
    for k = 1:numel(data.network.buses)
        bus = data.network.buses(k);
        buses(bus.id) = bus;
    end

    points = struct('plant', {}, 'bus', {}, 'vn_kv', {}, 'plant_mw', {}, ...
                    'sk_mva', {}, 'scr', {}, 'grid_r_ohm', {}, 'grid_l_h', {}, ...
                    'pll_bandwidth_hz', {}, 'strength', {});

    for k = 1:numel(data.network.generators)
        generator = data.network.generators(k);
        if ~strcmp(generator.technology, 'solar')
            continue
        end
        bus = buses(generator.bus);
        if isKey(levels, bus.id)
            sk = levels(bus.id);
        elseif bus.vn_kv <= 33
            sk = 300;                       % fall back, flagged in the report
        else
            sk = 1200;
        end

        if bus.vn_kv >= 150
            xOverR = 10;
        else
            xOverR = 6;
        end

        z = bus.vn_kv^2 / sk;
        r = z / hypot(1, xOverR);
        l = (r * xOverR) / (2 * pi * 50);
        scr = sk / generator.capacity_mw;

        if scr < 3
            strength = 'very weak';
        elseif scr < 5
            strength = 'weak';
        elseif scr < 10
            strength = 'moderate';
        else
            strength = 'strong';
        end

        points(end + 1) = struct( ...
            'plant', generator.id, 'bus', bus.id, 'vn_kv', bus.vn_kv, ...
            'plant_mw', generator.capacity_mw, 'sk_mva', sk, 'scr', scr, ...
            'grid_r_ohm', r, 'grid_l_h', l, ...
            'pll_bandwidth_hz', max(2, min(50, 2 * scr)), 'strength', strength); %#ok<AGROW>
    end
end
