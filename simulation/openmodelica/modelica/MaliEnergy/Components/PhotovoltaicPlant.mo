within MaliEnergy.Components;
model PhotovoltaicPlant
  "Inverter-based photovoltaic plant with optional frequency response"

  parameter Modelica.Units.SI.Power Prated = 50e6 "Rated alternating current power";
  parameter Real irradianceScale(unit = "1") = 1.0
    "Plane of array irradiance in per unit of 1000 W/m2";
  parameter Real temperatureDerate(unit = "1") = 0.88
    "Loss from cell temperature at Malian ambient conditions";
  parameter Boolean fastFrequencyResponse = false
    "Curtail below the maximum power point so the plant can respond upwards";
  parameter Real headroom(unit = "1") = 0.10
    "Curtailment held in reserve when fast frequency response is enabled";
  parameter Real droop(unit = "1") = 0.04 "Droop of the frequency response";
  parameter Modelica.Units.SI.Time Tinv = 0.05 "Inverter response time constant";
  parameter Modelica.Units.SI.Frequency fNom = 50 "Nominal frequency";

  Modelica.Blocks.Interfaces.RealInput f(unit = "Hz") "Measured frequency"
    annotation (Placement(transformation(extent = {{-120, -20}, {-80, 20}})));
  Modelica.Blocks.Interfaces.RealOutput P(unit = "W") "Electrical output"
    annotation (Placement(transformation(extent = {{100, -20}, {140, 20}})));

  Real Pavailable(unit = "1") "Power available from the array, per unit";
  Real Pset(unit = "1") "Set point, per unit";
  Real Pout(unit = "1", start = 0, fixed = true) "Delivered power, per unit";

equation
  Pavailable = min(1.0, irradianceScale * temperatureDerate);
  Pset = if fastFrequencyResponse then
           min(Pavailable,
               Pavailable * (1 - headroom) - (f - fNom) / fNom / droop * Pavailable)
         else
           Pavailable;
  der(Pout) = (min(Pavailable, max(0.0, Pset)) - Pout) / Tinv;
  P = Pout * Prated;

  annotation (Documentation(info = "<html>
<p>
With <code>fastFrequencyResponse = false</code>, which is how Malian plants are
operated today, the plant contributes nothing to arresting a frequency fall and
its capacity displaces machines that would have. Enabling it costs the
<code>headroom</code> in energy every hour of the year and buys a response that
acts in tens of milliseconds rather than seconds.
</p>
</html>"));
end PhotovoltaicPlant;
