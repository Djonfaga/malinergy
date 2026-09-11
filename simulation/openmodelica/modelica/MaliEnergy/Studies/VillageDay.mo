within MaliEnergy.Studies;
model VillageDay "A day in the life of a village mini-grid"
  extends MaliEnergy.Systems.VillageMinigrid;

  Modelica.Blocks.Sources.CombiTimeTable profiles(
    tableOnFile = true,
    tableName = "profiles",
    fileName = "village_profiles.txt",
    columns = {2, 3},
    extrapolation = Modelica.Blocks.Types.Extrapolation.Periodic)
    "Irradiance and demand, generated from the core dataset";

equation
  irradiance = profiles.y[1];
  loadShape = profiles.y[2];

  annotation (experiment(StopTime = 86400, Interval = 60), Documentation(info = "<html>
<p>The profile file is written by <code>mali_openmodelica.generate</code> from
the same photovoltaic model that feeds the load flow studies, so the mini-grid
sees the irradiance of a real Malian site rather than a sine wave.</p>
</html>"));
end VillageDay;
