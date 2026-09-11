within MaliEnergy.Components;
model SystemFrequency
  "Single-mass equivalent of the interconnected system frequency"

  parameter Modelica.Units.SI.Frequency fNom = 50 "Nominal frequency";
  parameter Real Hsys(unit = "s") = 4.2
    "Inertia constant of the synchronous fleet, on Sbase";
  parameter Modelica.Units.SI.Power Sbase = 500e6
    "Rating the inertia constant refers to";
  parameter Real D(unit = "1") = 1.5
    "Load damping, per unit power per unit frequency deviation";

  Modelica.Blocks.Interfaces.RealInput Pgen(unit = "W")
    "Total generation" annotation (Placement(transformation(extent = {{-120, 40}, {-80, 80}})));
  Modelica.Blocks.Interfaces.RealInput Pload(unit = "W")
    "Total demand" annotation (Placement(transformation(extent = {{-120, -80}, {-80, -40}})));
  Modelica.Blocks.Interfaces.RealOutput f(unit = "Hz", start = fNom, fixed = true)
    "System frequency" annotation (Placement(transformation(extent = {{100, -20}, {140, 20}})));

  Real df "Frequency deviation in per unit";
  Real rocof(unit = "Hz/s") "Rate of change of frequency";

equation
  df = (f - fNom) / fNom;
  // Swing equation of the aggregated rotating mass. The damping term is the
  // frequency sensitivity of the load itself, which in a system with a large
  // share of motors and no governor response is not negligible.
  2 * Hsys * Sbase / fNom * der(f) = Pgen - Pload - D * Sbase * df;
  rocof = der(f);

  annotation (Documentation(info = "<html>
<p>
The quantity that matters here is <code>Hsys * Sbase</code>, the stored kinetic
energy of the synchronous fleet in megawatt seconds. Photovoltaic plant does not
contribute to it, so every megawatt of solar that displaces a running machine
reduces it, and the rate of change of frequency after a trip rises in
proportion.
</p>
</html>"));
end SystemFrequency;
