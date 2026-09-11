within MaliEnergy.Components;
model DieselGenset "Diesel generating set with fuel consumption and minimum load"

  parameter Modelica.Units.SI.Power Prated = 100e3 "Rated power";
  parameter Real minLoad(unit = "1") = 0.30
    "Minimum loading; running below it glazes the bores and wastes fuel";
  parameter Real fuelNoLoad(unit = "1") = 0.08
    "No load fuel, in litres per hour per kilowatt of rating";
  parameter Real fuelSlope(unit = "1") = 0.25
    "Marginal fuel, in litres per kilowatt hour produced";
  parameter Modelica.Units.SI.Time Tstart = 20 "Time from start command to load";
  parameter Modelica.Units.SI.Time Tgov = 1.5 "Governor time constant";

  Modelica.Blocks.Interfaces.RealInput Pdemand(unit = "W") "Requested power"
    annotation (Placement(transformation(extent = {{-120, -20}, {-80, 20}})));
  Modelica.Blocks.Interfaces.BooleanInput running "Start command"
    annotation (Placement(transformation(extent = {{-120, 40}, {-80, 80}})));
  Modelica.Blocks.Interfaces.RealOutput P(unit = "W") "Delivered power"
    annotation (Placement(transformation(extent = {{100, 20}, {140, 60}})));
  Modelica.Blocks.Interfaces.RealOutput fuelLitres(start = 0, fixed = true)
    "Cumulative fuel consumption in litres"
    annotation (Placement(transformation(extent = {{100, -60}, {140, -20}})));

  Real Pcmd(unit = "W") "Command after the minimum load constraint";
  Real Pout(unit = "W", start = 0, fixed = true) "Delivered power";
  Real runHours(start = 0, fixed = true) "Cumulative running hours";

equation
  // A set that is asked for less than its minimum load runs at the minimum and
  // the surplus is wasted, which is the single largest avoidable cost in a
  // hybrid mini-grid.
  Pcmd = if not running then 0
         elseif Pdemand < minLoad * Prated then minLoad * Prated
         else min(Pdemand, Prated);
  der(Pout) = (Pcmd - Pout) / Tgov;
  P = Pout;
  der(fuelLitres) = if running then
      (fuelNoLoad * Prated / 1000 + fuelSlope * Pout / 1000) / 3600
    else 0;
  der(runHours) = if running then 1 / 3600 else 0;

  annotation (Documentation(info = "<html>
<p>
Fuel is modelled as an affine function of output, which is the standard
representation and is accurate to a few per cent above about a third of rating.
The no load term is what makes running a large set lightly loaded so expensive.
</p>
</html>"));
end DieselGenset;
