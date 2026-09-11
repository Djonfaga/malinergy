within ;
package MaliEnergy "Dynamic models of the Malian power system"
  extends Modelica.Icons.Package;

  annotation (
    uses(Modelica(version="4.0.0")),
    version="1.0.0",
    Documentation(info="<html>
<p>
Dynamic models of the Malian electricity system, built on the same catalogue
that feeds the steady-state studies in the rest of this repository. Two
questions are asked here that a load flow cannot answer:
</p>
<ul>
<li>What happens in the seconds after the largest unit trips, and how does that
change as photovoltaic capacity displaces synchronous machines?</li>
<li>How does a village mini-grid of panels, a battery and a diesel set behave
over a day and a year, and what does the diesel actually burn?</li>
</ul>
<p>
Parameters are generated from <code>build/mali_case.json</code> by
<code>mali_openmodelica.generate</code>, so the dynamic models and the load
flows describe the same system rather than two similar ones.
</p>
</html>"));
end MaliEnergy;
