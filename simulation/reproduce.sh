#!/usr/bin/env bash
# Reproduce every result in the repository, in the order they depend on.
#
# Run from the repository root on the sim/benchmark branch, which carries all
# five environments. On a single-tool branch the missing steps are skipped.
#
#   ./simulation/reproduce.sh            full run, three-hour annual sampling
#   ./simulation/reproduce.sh --quick    six-hour sampling, for a fast check
#
# PowerFactory and MATLAB are not invoked: both need licences. Their exports
# are produced and verified, and the scripts that drive them are printed at the
# end with the command to run them on a machine that has them.

set -euo pipefail

STEP_HOURS=3
[[ "${1:-}" == "--quick" ]] && STEP_HOURS=6

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

have() { [[ -f "simulation/$1/pyproject.toml" ]]; }
step() { printf '\n\033[1m== %s\033[0m\n' "$1"; }

step "Canonical dataset"
cd simulation/core
mali-energy fetch || echo "  (some sources unreachable; committed snapshots will be used)"
mali-energy validate
mali-energy build
mali-energy gaps | tail -3
cd "$ROOT"

if have pandapower; then
  step "pandapower: load flow, N-1, short circuit, annual run, hosting capacity"
  (cd simulation/pandapower && mali-pandapower --studies all --step-hours "$STEP_HOURS")
fi

if have pandapipes; then
  step "pandapipes: water supply, coupling, hydrogen"
  (cd simulation/pandapipes && mali-pandapipes --studies all)
fi

if have openmodelica; then
  step "OpenModelica: inertia, frequency response, mini-grid"
  (cd simulation/openmodelica && mali-openmodelica --studies all)
fi

if have simscape; then
  step "Simscape Electrical: grid strength, converter limits, ride-through"
  (cd simulation/simscape && mali-simscape --studies all)
fi

if have powerfactory; then
  step "PowerFactory: export and verify"
  (cd simulation/powerfactory && mali-powerfactory --output build)
fi

if have benchmark; then
  step "Benchmark: capability, effort, findings, comparison, figures"
  (cd simulation/benchmark && mali-benchmark --sections all --step-hours "$STEP_HOURS")
fi

step "Tests"
paths=""
for package in core pandapower pandapipes openmodelica simscape powerfactory benchmark; do
  [[ -d "simulation/$package/tests" ]] && paths="$paths simulation/$package/tests"
done
pytest -q --import-mode=importlib $paths

step "Not run here"
cat <<'NOTE'
  PowerFactory  import simulation/powerfactory/build/mali_dry_peak.dgs, then
                run mali_powerfactory/scripts/run_loadflow.py from a ComPython
                object, or: mali-powerfactory --run run_loadflow.py
  MATLAB        matlab -batch "addpath('.'); mali.runStudies()" from
                simulation/simscape/matlab
  OpenModelica  omc simulation/openmodelica/modelica/run_dry_peak.mos

  With any of those present, re-run:
      cd simulation/benchmark && mali-benchmark --sections compare
  to add their columns to the numerical comparison.
NOTE
