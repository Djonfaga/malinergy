within MaliEnergy.Studies;
model UnitTripDrySeason
  "Loss of a 40 MW unit at the dry season evening peak"
  extends MaliEnergy.Systems.InterconnectedFrequency(
    Hsys = 4.2, Pdemand = 385e6, Phydro = 74.4e6, Pthermal = 245e6,
    Psolar = 0, Pimport = 90e6, Ptrip = 40e6);
  annotation (experiment(StopTime = 60, Interval = 0.01), Documentation(info = "<html>
<p>The reference case: no sun, hydro at its April minimum, the whole thermal
fleet running. This is the fleet with the most inertia relative to demand that
the dry season offers.</p>
</html>"));
end UnitTripDrySeason;
