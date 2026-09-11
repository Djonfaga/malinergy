within MaliEnergy.Components;
model SynchronousUnit
  "Synchronous generating unit with a governor and a ramp limit"

  parameter Modelica.Units.SI.Power Prated = 40e6 "Rated active power";
  parameter Real Pinit(unit = "1") = 0.7 "Initial loading in per unit of rating";
  parameter Real droop(unit = "1") = 0.04 "Governor droop";
  parameter Modelica.Units.SI.Time Tg = 0.2 "Governor actuator time constant";
  parameter Modelica.Units.SI.Time Tt = 4.0
    "Prime mover time constant; hydro and heavy fuel oil sets are slow";
  parameter Real rampLimit(unit = "1/s") = 0.02
    "Maximum rate of change of output, per unit of rating per second";
  parameter Boolean governorEnabled = true
    "False for a unit running at a fixed output";
  parameter Modelica.Units.SI.Frequency fNom = 50 "Nominal frequency";

  Modelica.Blocks.Interfaces.RealInput f(unit = "Hz") "Measured frequency"
    annotation (Placement(transformation(extent = {{-120, -20}, {-80, 20}})));
  Modelica.Blocks.Interfaces.RealOutput P(unit = "W") "Electrical output"
    annotation (Placement(transformation(extent = {{100, -20}, {140, 20}})));

  Real Pref(unit = "1") "Governor reference in per unit";
  Real Pvalve(unit = "1", start = Pinit, fixed = true) "Valve or gate position";
  Real Pmech(unit = "1", start = Pinit, fixed = true) "Mechanical power";

equation
  // Droop: a frequency fall of droop x fNom calls for full output.
  Pref = if governorEnabled then Pinit - (f - fNom) / fNom / droop else Pinit;
  // The actuator moves towards the reference, limited in rate.
  der(Pvalve) = min(rampLimit, max(-rampLimit, (min(1.0, max(0.0, Pref)) - Pvalve) / Tg));
  // The prime mover follows the actuator with its own lag.
  der(Pmech) = (Pvalve - Pmech) / Tt;
  P = Pmech * Prated;

  annotation (Documentation(info = "<html>
<p>
The ramp limit is what distinguishes the Malian fleet from a textbook one.
Manantali and Selingue are hydro sets that can move quickly; the heavy fuel oil
engines at Kayes and Balingue cannot, and the difference decides whether the
frequency recovers before load shedding relays operate.
</p>
</html>"));
end SynchronousUnit;
