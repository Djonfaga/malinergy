# PowerFactory — the Malian interconnected network

PowerFactory is licensed software and cannot run in this repository's checks.
What this branch does instead is produce the project in the format PowerFactory
imports natively, verify that export against the source data, and ship the
automation scripts that run the studies once it is loaded.

```bash
pip install -e simulation/core -e simulation/powerfactory
mali-energy build                 # in simulation/core
mali-powerfactory --output build  # export and verify all four cases
pytest simulation/powerfactory    # 16 checks
```

```
  dry_peak    -> build/mali_dry_peak.dgs    (33 busbars, 25 lines, 9 machines)  verification: ok
  wet_peak    -> build/mali_wet_peak.dgs    (33 busbars, 25 lines, 9 machines)  verification: ok
  solar_noon  -> build/mali_solar_noon.dgs  (33 busbars, 25 lines, 9 machines)  verification: ok
  night_min   -> build/mali_night_min.dgs   (33 busbars, 25 lines, 9 machines)  verification: ok
```

See `docs/importing.md` for the import steps and what each file contains.

## Verifying an export you cannot run

The export is the only thing that crosses into PowerFactory, so it is checked
harder than anything else here. `mali_powerfactory.verify` reads the file back
the way an importer would and confirms:

- every busbar, line, transformer, shunt and load in the source is present;
- every row matches its header width, because a short row is a malformed row
  and padding it would hide the problem;
- every reference — folder, terminal, type — resolves to an object that exists;
- line resistance, reactance and capacitance are unchanged from the catalogue,
  and zero-sequence reactance exceeds positive-sequence;
- the generation PowerFactory would see equals the dispatch in the case;
- there is exactly one slack node.

Two of those checks exist because they caught something.

**The dispatch check caught a real bug.** PowerFactory multiplies `pgini` by
`ngnum`: the attribute is the output of one machine, not of the station. The
first export wrote the station total against a machine count, and PowerFactory
would have seen **2 412 MW of generation against a 319 MW case** — a load flow
that converges perfectly and is wrong by a factor of seven. The verifier now
fails the export when the product differs from the case by more than one per
cent, and a test asserts the per-machine division.

**The corruption checks exist so the verifier proves something.** Two tests
deliberately damage an export — drop three busbars, point a line at an
identifier that does not exist — and require the verifier to fail. A checker
that has never failed is not a checker.

## What the comparison is for

This is the commercial tool in the benchmark, and the interesting result is not
whether it agrees with pandapower on a load flow — it will. It is what it does
that the open tools made us write by hand:

| Done here by an object | Written by hand in `sim/pandapower` |
|---|---|
| Station controller switching capacitor banks | `operations.switch_shunts`, with oscillation detection |
| Active power balancing across machines | `operations.rebalance_dispatch`, iterating until the slack matches |
| Contingency analysis with post-fault actions | `studies.contingency.run_n1`, including isolated-demand accounting |
| RMS dynamics with standard machine and governor models | the Modelica library in `sim/openmodelica`, plus a SciPy reference |

Each of those took real effort in the open-source branch and each is a checkbox
here. What that convenience is worth — against a licence, and against the
transparency of code you can read — is the question `sim/benchmark` puts
numbers to.

## Layout

```
mali_powerfactory/
  dgs.py        canonical case -> DGS interchange format
  verify.py     read the export back and check it against the source
  api.py        external engine access, honest about what is installed
  cli.py        mali-powerfactory
  scripts/      run inside PowerFactory
    run_loadflow.py      four operating points, taps and shunts active
    run_shortcircuit.py  IEC 60909, three-phase and earth, max and min
    run_contingency.py   N-1 with the built-in contingency object
    run_rms.py           loss of the largest infeed, for the Modelica comparison
docs/importing.md
```
