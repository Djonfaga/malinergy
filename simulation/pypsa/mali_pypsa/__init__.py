"""Single-node PyPSA model of the Malian power system.

Version 0.1. The scope is deliberately small and stated in the README: one
node, the EDM-SA generation fleet, an annual hourly demand profile, a solar
resource, and a least-cost dispatch. No network, no capacity expansion, no
storage optimisation — those are later versions, and claiming them now would
make the model harder to check rather than more useful.

Everything the model knows about the Malian system comes from the shared
catalogue in ``simulation/core``, so this model and the power-flow studies in
the sibling branches describe the same fleet rather than two similar ones.
"""

__version__ = "0.1.0"
