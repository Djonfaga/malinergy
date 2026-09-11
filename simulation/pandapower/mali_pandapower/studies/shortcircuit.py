"""Short-circuit currents to IEC 60909.

Maximum currents size the switchgear; minimum currents decide whether a
protection relay can see a fault at all. Both are computed, because a network
built largely of long radial 225 kV corridors fed at one end has minimum
single-phase fault currents that can fall close to load current at the remote
end — which is a protection-coordination problem, not a rating problem.
"""

from __future__ import annotations

import pandapower as pp
import pandapower.shortcircuit as sc
import pandas as pd

from ..builder import build


def run_short_circuit(
    exchange: dict,
    case_name: str = "dry_peak",
    *,
    fault_types: tuple[str, ...] = ("3ph", "1ph"),
) -> pd.DataFrame:
    """Initial symmetrical short-circuit current at every busbar.

    Returns one row per bus with maximum and minimum currents for each fault
    type, the peak current, and the breaking capacity the busbar needs.
    """
    frames: list[pd.DataFrame] = []

    for fault in fault_types:
        for kind in ("max", "min"):
            result = build(exchange, case_name)
            net = result.net
            try:
                sc.calc_sc(
                    net,
                    fault=fault,
                    case=kind,
                    lv_tol_percent=10,
                    topology="auto",
                    ip=True,
                    ith=True,
                    branch_results=False,
                    return_all_currents=False,
                    inverse_y=False,
                )
            except Exception as exc:  # noqa: BLE001 - reported, not hidden
                frames.append(
                    pd.DataFrame(
                        {
                            "bus": net.bus.name,
                            "vn_kv": net.bus.vn_kv,
                            f"ikss_{fault}_{kind}_ka": float("nan"),
                            "error": str(exc)[:120],
                        }
                    )
                )
                continue

            data = {
                "bus": net.bus.name,
                "vn_kv": net.bus.vn_kv,
                "zone": net.bus.zone,
                f"ikss_{fault}_{kind}_ka": net.res_bus_sc.ikss_ka.round(3),
            }
            if kind == "max" and "ip_ka" in net.res_bus_sc:
                data[f"ip_{fault}_ka"] = net.res_bus_sc.ip_ka.round(3)
            if kind == "max" and "ith_ka" in net.res_bus_sc:
                data[f"ith_{fault}_ka"] = net.res_bus_sc.ith_ka.round(3)
            frames.append(pd.DataFrame(data))

    merged = frames[0]
    for frame in frames[1:]:
        new_columns = [c for c in frame.columns if c not in merged.columns]
        merged = merged.join(frame[new_columns])

    if "ikss_3ph_max_ka" in merged:
        # Short-circuit power, the number switchgear is specified against.
        merged["sk_max_mva"] = (
            3**0.5 * merged["vn_kv"] * merged["ikss_3ph_max_ka"]
        ).round(1)
    if {"ikss_3ph_max_ka", "ikss_3ph_min_ka"} <= set(merged.columns):
        merged["min_max_ratio"] = (
            merged["ikss_3ph_min_ka"] / merged["ikss_3ph_max_ka"]
        ).round(3)

    return merged.sort_values(["vn_kv", "sk_max_mva"], ascending=[False, False]).reset_index(
        drop=True
    )


def earthing_review(frame: pd.DataFrame) -> pd.DataFrame:
    """Busbars with no zero-sequence source, and those where an earth fault
    exceeds a three-phase fault.

    Both are findings rather than errors. A busbar fed only from a delta
    winding has no path for earth-fault current in the model: the catalogue
    contains no earthing transformer, so a single-phase fault there returns
    almost nothing and no earth-fault protection could be set from this study.
    At the other end, a busbar sitting on a solidly earthed neutral has a lower
    zero-sequence impedance than positive-sequence, which puts the
    single-phase current above the three-phase one and is what sizes the
    switchgear.
    """
    if not {"ikss_1ph_max_ka", "ikss_3ph_max_ka"} <= set(frame.columns):
        return pd.DataFrame()
    working = frame.copy()
    working["ratio_1ph_3ph"] = (
        working["ikss_1ph_max_ka"] / working["ikss_3ph_max_ka"]
    ).round(3)

    def classify(row):
        if row["ikss_1ph_max_ka"] < 0.05:
            return "no zero-sequence source: add an earthing transformer before setting earth-fault protection"
        if row["ratio_1ph_3ph"] > 1.0:
            return "earth fault exceeds three-phase fault: this is what sizes the switchgear here"
        return "conventional"

    working["finding"] = working.apply(classify, axis=1)
    notable = working[working["finding"] != "conventional"]
    return notable[
        ["bus", "vn_kv", "ikss_3ph_max_ka", "ikss_1ph_max_ka", "ratio_1ph_3ph", "finding"]
    ].reset_index(drop=True)


def protection_margin(frame: pd.DataFrame, load_current_ka: float = 0.3) -> pd.DataFrame:
    """Busbars where the minimum fault current is uncomfortably close to load.

    A distance or overcurrent relay needs a clear separation between the
    smallest fault it must trip for and the largest load it must not trip for.
    Under a factor of two the setting becomes a compromise.
    """
    if "ikss_1ph_min_ka" not in frame.columns:
        return pd.DataFrame()
    working = frame.copy()
    working["margin"] = (working["ikss_1ph_min_ka"] / load_current_ka).round(2)
    tight = working[working["margin"] < 2.0]
    return tight[["bus", "vn_kv", "ikss_1ph_min_ka", "margin"]].reset_index(drop=True)
