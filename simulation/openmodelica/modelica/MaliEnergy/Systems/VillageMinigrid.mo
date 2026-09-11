within MaliEnergy.Systems;
model VillageMinigrid
  "Photovoltaic, battery and diesel mini-grid for a Malian village"

  parameter Modelica.Units.SI.Power Ppv = 150e3 "Photovoltaic capacity";
  parameter Modelica.Units.SI.Power Pdiesel = 100e3 "Diesel set rating";
  parameter Modelica.Units.SI.Power Pbattery = 80e3 "Battery converter rating";
  parameter Modelica.Units.SI.Energy Ebattery = 320e3 * 3600 "Battery energy";
  parameter Modelica.Units.SI.Power Ppeak = 120e3 "Peak village demand";
  parameter Real socStartDiesel(unit = "1") = 0.25
    "State of charge below which the diesel set is started";
  parameter Real socStopDiesel(unit = "1") = 0.60
    "State of charge at which it is stopped again";

  Components.PhotovoltaicPlant pv(Prated = Ppv);
  Components.BatteryStorage battery(Prated = Pbattery, Erated = Ebattery);
  Components.DieselGenset genset(Prated = Pdiesel);

  input Real irradiance(unit = "1") "Plane of array irradiance, per unit";
  input Real loadShape(unit = "1") "Demand, per unit of peak";

  Modelica.Units.SI.Power Pload "Village demand";
  Modelica.Units.SI.Power Pnet "Demand not met by the array";
  Modelica.Units.SI.Power Pcurtailed "Photovoltaic power with nowhere to go";
  Modelica.Units.SI.Power Punserved "Demand that cannot be met";
  Boolean dieselRunning(start = false, fixed = true);
  Boolean powerShort "Demand above what the battery converter can deliver";

equation
  pv.irradianceScale = irradiance;
  pv.f = 50;
  Pload = Ppeak * loadShape;
  Pnet = Pload - pv.P;

  // Two start conditions, and both are needed. The state of charge covers the
  // energy case, with hysteresis between the start and stop thresholds so the
  // set does not cycle. The power condition covers the case a controller
  // watching only the state of charge misses: the battery converter is rated
  // below the village peak, so on a full battery it can still fail to cover
  // the evening load, and the village is shed with the storage full.
  powerShort = Pnet > Pbattery;
  dieselRunning = (battery.soc < socStartDiesel) or powerShort
                  or (pre(dieselRunning) and battery.soc < socStopDiesel);
  genset.running = dieselRunning;
  genset.Pdemand = max(0, Pnet - battery.P);

  battery.Pdemand = if Pnet > 0 then min(Pnet, Pbattery) else max(Pnet, -Pbattery);

  Pcurtailed = max(0, -Pnet - (if battery.P < 0 then -battery.P else 0));
  Punserved = max(0, Pload - pv.P - battery.P - genset.P);

  annotation (
    experiment(StartTime = 0, StopTime = 86400, Tolerance = 1e-6, Interval = 60),
    Documentation(info = "<html>
<p>
The dispatch rule is the one used on real Malian mini-grids: the array serves
the load, the battery absorbs the difference, and the diesel set runs only when
the state of charge falls below a start threshold, then charges the battery back
up to a stop threshold before shutting down. The hysteresis between the two
thresholds is what keeps the set from cycling.
</p>
<p>
The outputs to look at are <code>genset.fuelLitres</code>,
<code>genset.runHours</code> and <code>Pcurtailed</code>: fuel is the operating
cost, running hours are the maintenance cost, and curtailed energy is the
capital that was spent and is not being used.
</p>
</html>"));
end VillageMinigrid;
