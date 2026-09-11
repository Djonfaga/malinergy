within MaliEnergy.Studies;
model UnitTripHighSolar
  "The same trip at midday with 200 MW of photovoltaic plant displacing machines"
  extends MaliEnergy.Systems.InterconnectedFrequency(
    Hsys = 2.4, Pdemand = 454e6, Phydro = 74.4e6, Pthermal = 125e6,
    Psolar = 200e6, Pimport = 90e6, Ptrip = 40e6);
  annotation (experiment(StopTime = 60, Interval = 0.01), Documentation(info = "<html>
<p>The same 40 MW trip, but the thermal plant that was running in the dry season
case has been backed off to take the solar output. The stored energy of the
fleet falls with it, and the rate of change of frequency after the trip rises in
proportion.</p>
</html>"));
end UnitTripHighSolar;
