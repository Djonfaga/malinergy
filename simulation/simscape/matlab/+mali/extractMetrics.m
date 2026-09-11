function metrics = extractMetrics(simOut, p)
%EXTRACTMETRICS Reduce a simulation run to the same figures the Python
%reference reports, so the two implementations can be compared directly.

    logged = simOut.get('logsout');
    time = logged.get('Ppu').Values.Time;
    power = logged.get('Ppu').Values.Data;
    angle = logged.get('AngleError').Values.Data;
    current = logged.get('Ipu').Values.Data;

    tail = time >= time(end) * 0.75;
    ripple = max(power(tail)) - min(power(tail));
    diverged = any(~isfinite(power)) || max(abs(current)) > 5 || max(abs(angle)) > pi;

    metrics = struct();
    metrics.name = p.name;
    metrics.scr = p.scr;
    metrics.pll_bandwidth_hz = p.pllBandwidth;
    metrics.stable = ~diverged && ripple < 0.02;
    metrics.diverged = diverged;
    metrics.power_ripple_pu = ripple;
    metrics.final_p_pu = power(end);
    metrics.max_angle_error_deg = max(abs(angle)) * 180 / pi;
    metrics.max_current_pu = max(abs(current));
end
