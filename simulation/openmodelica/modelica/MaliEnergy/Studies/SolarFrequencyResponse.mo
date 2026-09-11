within MaliEnergy.Studies;
model SolarFrequencyResponse
  "The high solar case with the plants curtailed so they can respond"
  extends MaliEnergy.Systems.InterconnectedFrequency(
    Hsys = 2.4, Pdemand = 454e6, Phydro = 74.4e6, Pthermal = 125e6,
    Psolar = 200e6, Pimport = 90e6, Ptrip = 40e6,
    solarProvidesResponse = true);
  annotation (experiment(StopTime = 60, Interval = 0.01), Documentation(info = "<html>
<p>Ten per cent of headroom held on the photovoltaic plant, released on droop.
The cost is ten per cent of the solar energy every hour of every day; the
benefit is the difference between this frequency trace and the one in
UnitTripHighSolar.</p>
</html>"));
end SolarFrequencyResponse;
