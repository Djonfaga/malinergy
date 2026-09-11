function p = inverterParameters(point, varargin)
%INVERTERPARAMETERS Plant and controller parameters for one connection point.
%
%   Mirrors mali_simscape.reference.InverterDesign in the Python
%   implementation, so the two can be compared directly. Two choices here
%   decide whether a weak-grid study means anything:
%
%   * the current controller decouples with the FILTER inductance, not the
%     total. Decoupling with the total cancels the network impedance exactly
%     and the weak-grid problem disappears from the model rather than from the
%     plant;
%   * a control delay of one and a half sample periods is represented. It is
%     the other half of the weak-grid mechanism.

    parser = inputParser;
    addParameter(parser, 'PllBandwidthHz', []);
    addParameter(parser, 'CurrentBandwidthHz', 300);
    addParameter(parser, 'FilterLpu', 0.10);
    addParameter(parser, 'FilterRpu', 0.005);
    addParameter(parser, 'ControlDelay', 3e-4);
    addParameter(parser, 'PllDamping', 0.707);
    addParameter(parser, 'Psetpoint', 0.9);
    addParameter(parser, 'Qsetpoint', 0.0);
    parse(parser, varargin{:});
    opts = parser.Results;

    p = struct();
    p.name = point.plant;
    p.Vbase = point.vn_kv * 1e3;
    p.Sbase = point.plant_mw * 1e6 / 0.95;
    p.fNom = 50;
    p.wNom = 2 * pi * p.fNom;
    p.Zbase = p.Vbase^2 / p.Sbase;
    p.Ibase = p.Sbase / (sqrt(3) * p.Vbase);

    p.Lf = opts.FilterLpu * p.Zbase / p.wNom;
    p.Rf = opts.FilterRpu * p.Zbase;
    p.Lg = point.grid_l_h;
    p.Rg = point.grid_r_ohm;
    p.scr = point.scr;

    if isempty(opts.PllBandwidthHz)
        p.pllBandwidth = point.pll_bandwidth_hz;
    else
        p.pllBandwidth = opts.PllBandwidthHz;
    end
    p.currentBandwidth = opts.CurrentBandwidthHz;
    p.controlDelay = opts.ControlDelay;

    % Internal model control: the loop cancels the plant pole.
    p.Kp_i = 2 * pi * p.currentBandwidth * p.Lf;
    p.Ki_i = 2 * pi * p.currentBandwidth * p.Rf;

    wPll = 2 * pi * p.pllBandwidth;
    p.Kp_pll = 2 * opts.PllDamping * wPll;
    p.Ki_pll = wPll^2;

    p.Pset = opts.Psetpoint;
    p.Qset = opts.Qsetpoint;
    p.currentLimit = 1.2;
end
