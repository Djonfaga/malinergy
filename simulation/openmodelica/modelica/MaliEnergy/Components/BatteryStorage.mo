within MaliEnergy.Components;
model BatteryStorage "Battery with state of charge and round trip efficiency"

  parameter Modelica.Units.SI.Power Prated = 1e6 "Converter rating";
  parameter Modelica.Units.SI.Energy Erated = 4 * 3600e3 "Usable energy";
  parameter Real socInit(unit = "1") = 0.6 "Initial state of charge";
  parameter Real socMin(unit = "1") = 0.15 "Lower limit, protecting cycle life";
  parameter Real socMax(unit = "1") = 0.95 "Upper limit";
  parameter Real etaCharge(unit = "1") = 0.95 "Charging efficiency";
  parameter Real etaDischarge(unit = "1") = 0.95 "Discharging efficiency";
  parameter Modelica.Units.SI.Time Tconv = 0.02 "Converter response time constant";

  Modelica.Blocks.Interfaces.RealInput Pdemand(unit = "W")
    "Requested power, positive when discharging"
    annotation (Placement(transformation(extent = {{-120, -20}, {-80, 20}})));
  Modelica.Blocks.Interfaces.RealOutput P(unit = "W") "Delivered power"
    annotation (Placement(transformation(extent = {{100, -20}, {140, 20}})));
  Modelica.Blocks.Interfaces.RealOutput soc(unit = "1", start = socInit, fixed = true)
    "State of charge"
    annotation (Placement(transformation(extent = {{100, -80}, {140, -40}})));

  Real Pcmd(unit = "W") "Command after limits";
  Real Pactual(unit = "W", start = 0, fixed = true) "Converter output";

equation
  // The state of charge limits what can be asked for in either direction.
  Pcmd = if Pdemand > 0 then
           (if soc > socMin then min(Pdemand, Prated) else 0)
         else
           (if soc < socMax then max(Pdemand, -Prated) else 0);
  der(Pactual) = (Pcmd - Pactual) / Tconv;
  P = Pactual;
  // Losses fall on the side of the converter that is active.
  der(soc) = if Pactual > 0 then -Pactual / etaDischarge / Erated
             else -Pactual * etaCharge / Erated;

  annotation (Documentation(info = "<html>
<p>
The state of charge limits are not decoration. A village battery cycled between
zero and full is a battery replaced in three years instead of ten, and the
economics of a Malian mini-grid do not survive that.
</p>
</html>"));
end BatteryStorage;
