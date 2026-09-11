within MaliEnergy.Components;
model AggregateLoad "Demand with frequency and voltage sensitivity"

  parameter Modelica.Units.SI.Power Pnom = 400e6 "Demand at nominal frequency";
  parameter Real kf(unit = "1") = 1.5
    "Frequency sensitivity, per unit power per unit frequency";
  parameter Modelica.Units.SI.Frequency fNom = 50 "Nominal frequency";
  parameter Boolean underFrequencyShedding = true
    "Enable the load shedding relays";
  parameter Real shedStages[:] = {49.0, 48.7, 48.4, 48.1}
    "Frequency at which each stage operates";
  parameter Real shedFraction[:] = {0.05, 0.05, 0.05, 0.05}
    "Demand disconnected at each stage";

  Modelica.Blocks.Interfaces.RealInput f(unit = "Hz") "System frequency"
    annotation (Placement(transformation(extent = {{-120, -20}, {-80, 20}})));
  Modelica.Blocks.Interfaces.RealOutput P(unit = "W") "Demand"
    annotation (Placement(transformation(extent = {{100, -20}, {140, 20}})));
  Modelica.Blocks.Interfaces.RealOutput shed(unit = "1", start = 0, fixed = true)
    "Fraction of demand disconnected"
    annotation (Placement(transformation(extent = {{100, -80}, {140, -40}})));

  Boolean stageTripped[size(shedStages, 1)](each start = false, each fixed = true);

equation
  for i in 1:size(shedStages, 1) loop
    stageTripped[i] = underFrequencyShedding and (f < shedStages[i] or pre(stageTripped[i]));
  end for;
  shed = sum(if stageTripped[i] then shedFraction[i] else 0.0
             for i in 1:size(shedStages, 1));
  P = Pnom * (1 - shed) * (1 + kf * (f - fNom) / fNom);

  annotation (Documentation(info = "<html>
<p>
Under-frequency load shedding is included because without it the frequency
response of a small system looks far worse than it is: the relays are the last
line of defence and they work. The stages follow the usual West African
practice of five per cent steps from 49 Hz downwards.
</p>
</html>"));
end AggregateLoad;
