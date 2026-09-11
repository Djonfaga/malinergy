within MaliEnergy.Systems;
model InterconnectedFrequency
  "Frequency response of the Malian interconnected network to a unit trip"

  // Parameters below are written by mali_openmodelica.generate from
  // build/mali_case.json, so this model and the load flows describe the same
  // dispatch. The defaults reproduce the dry season evening peak of 2024.

  parameter Modelica.Units.SI.Power Sbase = 500e6 "System base";
  parameter Real Hsys(unit = "s") = 4.2 "Inertia constant of the running fleet";
  parameter Modelica.Units.SI.Power Pdemand = 385e6 "Demand at the operating point";
  parameter Modelica.Units.SI.Power Phydro = 74.4e6 "Hydro output";
  parameter Modelica.Units.SI.Power Pthermal = 245e6 "Thermal output";
  parameter Modelica.Units.SI.Power Psolar = 0 "Photovoltaic output";
  parameter Modelica.Units.SI.Power Pimport = 90e6 "Net import, held constant";
  parameter Modelica.Units.SI.Power Ptrip = 40e6 "Generation lost in the event";
  parameter Modelica.Units.SI.Time tTrip = 5 "Time of the trip";
  parameter Boolean solarProvidesResponse = false
    "Whether the photovoltaic plant is curtailed so it can respond";

  Components.SystemFrequency grid(Sbase = Sbase, Hsys = Hsys);
  Components.SynchronousUnit hydro(
    Prated = Phydro, Pinit = 1.0, droop = 0.04, Tt = 2.0, rampLimit = 0.05);
  Components.SynchronousUnit thermal(
    Prated = Pthermal, Pinit = 1.0, droop = 0.04, Tt = 6.0, rampLimit = 0.01);
  Components.PhotovoltaicPlant solar(
    Prated = max(Psolar, 1), irradianceScale = if Psolar > 0 then 1.0 else 0.0,
    fastFrequencyResponse = solarProvidesResponse);
  Components.AggregateLoad demand(Pnom = Pdemand);

  Modelica.Units.SI.Power Ptripped "Generation removed by the event";
  Modelica.Units.SI.Power Pgen "Total generation";
  Modelica.Units.SI.Frequency fNadir(start = 50, fixed = true) "Lowest frequency reached";

equation
  Ptripped = if time < tTrip then 0 else Ptrip;

  connect(grid.f, hydro.f);
  connect(grid.f, thermal.f);
  connect(grid.f, solar.f);
  connect(grid.f, demand.f);

  Pgen = hydro.P + thermal.P + solar.P + Pimport - Ptripped;
  connect(Pgen, grid.Pgen);
  connect(demand.P, grid.Pload);

  der(fNadir) = if grid.f < fNadir then der(grid.f) else 0;

  annotation (
    experiment(StartTime = 0, StopTime = 60, Tolerance = 1e-6, Interval = 0.01),
    Documentation(info = "<html>
<p>
The question this model exists to answer: the Malian system carries roughly
2 200 MW.s of stored kinetic energy at the dry season peak. Losing a 40 MW unit
from that base gives an initial rate of change of frequency near
0.45 Hz/s. Replace running machines with photovoltaic capacity and the stored
energy falls while the largest single infeed does not, so the same trip becomes
progressively harder to ride through.
</p>
</html>"));
end InterconnectedFrequency;
