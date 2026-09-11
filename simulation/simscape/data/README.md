# Inputs produced by another branch

`shortcircuit_dry_peak.csv` holds the initial symmetrical short-circuit current
at every busbar, computed to IEC 60909 on the dry-season peak case by the
pandapower branch of this repository. It is committed here because the
converter studies need it and because a number that crosses a branch boundary
should be visible rather than recomputed differently on each side.

To regenerate it:

```bash
git checkout sim/pandapower
mali-energy build
mali-pandapower --studies shortcircuit --case dry_peak
# results/shortcircuit_dry_peak.csv
```

Every row is `derived`: it comes from the catalogue impedances, not from a
measurement. When EDM-SA fault-level records replace the catalogue estimates,
regenerate this file rather than editing it.
